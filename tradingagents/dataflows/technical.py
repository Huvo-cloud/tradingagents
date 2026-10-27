"""Deterministic technical context; no broker connectivity or order placement."""
from dataclasses import dataclass
import math
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class Config:
    pivot_window: int = 3
    tolerance_atr: float = 0.5
    tolerance_price: float = 0.005
    horizons: tuple = (('short', 63), ('medium', 126), ('long', 252))


def validate(data):
    d = data.copy()
    d.columns = [str(c).lower().replace(' ', '_') for c in d.columns]
    required = ['open', 'high', 'low', 'close', 'volume']
    if not set(required).issubset(d.columns):
        raise ValueError('Required columns: Open, High, Low, Close, Volume')
    if not isinstance(d.index, pd.DatetimeIndex) or d.index.has_duplicates or not d.index.is_monotonic_increasing:
        raise ValueError('Index must be a unique ascending DatetimeIndex')
    d[required] = d[required].apply(pd.to_numeric, errors='coerce')
    if d[required].isna().any().any() or not np.isfinite(d[required]).all().all():
        raise ValueError('Missing or non-finite OHLCV values')
    if (d[['open','high','low','close']] <= 0).any().any() or (d.volume < 0).any():
        raise ValueError('Prices must be positive and volume nonnegative')
    if ((d.high < d[['open','close','low']].max(axis=1)) | (d.low > d[['open','close','high']].min(axis=1))).any():
        raise ValueError('Inconsistent OHLC values')
    if len(d) < 35:
        raise ValueError('At least 35 observations are required')
    return d


def indicators(d):
    c = d.close
    out = pd.DataFrame(index=d.index)
    for n in (20, 50, 200): out[f'sma{n}'] = c.rolling(n, min_periods=n).mean()
    delta = c.diff(); gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
    # Wilder average with simple initial seed.
    def wilder(s, n):
        result = pd.Series(np.nan, index=s.index, dtype=float)
        vals = s.to_numpy(dtype=float)
        good = np.flatnonzero(np.isfinite(vals))
        if len(good) < n: return result
        start = good[0] + n - 1
        if start >= len(vals) or not np.isfinite(vals[good[0]:start+1]).all(): return result
        result.iloc[start] = vals[good[0]:start+1].mean()
        for i in range(start+1, len(vals)): result.iloc[i] = (result.iloc[i-1]*(n-1)+vals[i])/n
        return result
    ag, al = wilder(gain,14), wilder(loss,14)
    out['rsi14'] = (100 - 100/(1+ag/al)).mask((ag == 0)&(al == 0), 50).mask((ag > 0)&(al == 0),100)
    e12 = c.ewm(span=12, adjust=False, min_periods=12).mean(); e26 = c.ewm(span=26, adjust=False, min_periods=26).mean()
    out['macd'] = e12-e26; out['macd_signal'] = out.macd.ewm(span=9, adjust=False, min_periods=9).mean(); out['macd_hist'] = out.macd-out.macd_signal
    tr = pd.concat([d.high-d.low, (d.high-c.shift()).abs(), (d.low-c.shift()).abs()],axis=1).max(axis=1)
    out['atr14'] = wilder(tr,14)
    out['atr_pct'] = out.atr14/c*100
    out['vwma20'] = (c*d.volume).rolling(20).sum()/d.volume.rolling(20).sum().replace(0,np.nan)
    out['volume_sma20'] = d.volume.rolling(20).mean()
    out['volume_ratio'] = d.volume / out.volume_sma20.replace(0,np.nan)
    out['realized_vol20_annualized_pct'] = c.pct_change().rolling(20).std(ddof=1)*np.sqrt(252)*100
    return out


def pivots(d, window):
    if window < 1: raise ValueError('pivot_window must be >= 1')
    result=[]
    for i in range(window,len(d)-window):
        h=d.high.iloc[i-window:i+window+1]; l=d.low.iloc[i-window:i+window+1]
        # Strict uniqueness discards plateaus and outside bars that are both high and low.
        hi=d.high.iloc[i] == h.max() and (h == h.max()).sum()==1
        lo=d.low.iloc[i] == l.min() and (l == l.min()).sum()==1
        if hi != lo: result.append({'pos':i,'date':str(d.index[i].date()),'kind':'high' if hi else 'low','price':float(d.high.iloc[i] if hi else d.low.iloc[i])})
    return result


def swing(d, window):
    p=pivots(d,window)
    # Latest confirmed pivot plus the nearest preceding opposite pivot that forms a valid move.
    for end in reversed(p):
        for start in reversed([v for v in p if v['pos'] < end['pos'] and v['kind'] != end['kind']]):
            if (end['kind']=='high' and end['price']>start['price']) or (end['kind']=='low' and end['price']<start['price']):
                return start,end
    return None


def analyze(data, as_of=None, config=Config()):
    d=validate(data)
    if as_of is not None:
        cutoff=pd.Timestamp(as_of)
        if d.index.tz is not None and cutoff.tzinfo is None: cutoff=cutoff.tz_localize(d.index.tz)
        d=d.loc[d.index <= cutoff]
        if len(d)<35: raise ValueError('Insufficient data on or before as_of')
    if config.tolerance_atr <= 0 or config.tolerance_price <= 0: raise ValueError('Tolerances must be positive')
    ind=indicators(d); last=ind.iloc[-1]; price=float(d.close.iloc[-1]); atr=float(last.atr14)
    tol=max(config.tolerance_atr*atr, config.tolerance_price*price)
    levels=[]; swings={}; warnings=[]
    for name, bars in config.horizons:
        sub=d.iloc[-bars:]; pair=swing(sub,config.pivot_window)
        if len(sub)<bars: warnings.append(f'{name}: only {len(sub)}/{bars} bars available')
        if not pair:
            swings[name]=None; warnings.append(f'{name}: no confirmed valid swing'); continue
        a,b=pair; direction='up' if b['kind']=='high' else 'down'; dist=abs(b['price']-a['price']); sign=1 if direction=='up' else -1
        swings[name]={'direction':direction,'start':a,'end':b,'confirmation_bars':config.pivot_window}
        for ratio in (0.236,0.382,0.5,0.618,0.786):
            levels.append({'price':b['price']-sign*dist*ratio,'family':'fibonacci','label':f'{name} retracement {ratio:.3f}'})
        for ratio in (1.272,1.618):
            levels.append({'price':a['price']+sign*dist*ratio,'family':'fibonacci','label':f'{name} extension {ratio:.3f}'})
        for p in pivots(sub,config.pivot_window)[-6:]:
            levels.append({'price':p['price'],'family':'pivot','label':f"{name} {p['kind']} {p['date']}"})
    for n in (20,50,200):
        v=last[f'sma{n}']
        if pd.notna(v): levels.append({'price':float(v),'family':f'sma{n}','label':f'SMA{n}'})
        else: warnings.append(f'SMA{n} unavailable: insufficient history')
    levels=[x for x in levels if x['price']>0 and math.isfinite(x['price'])]; levels.sort(key=lambda x:x['price'])
    # Complete-link clustering: total width never exceeds tolerance; no transitive chaining.
    groups=[]
    for level in levels:
        if not groups or level['price']-groups[-1][0]['price'] > tol: groups.append([level])
        else: groups[-1].append(level)
    zones=[]
    for group in groups:
        families=sorted(set(x['family'] for x in group))
        lo,hi=group[0]['price'],group[-1]['price']; mid=(lo+hi)/2
        role='support / potential entry or re-entry' if hi < price else ('resistance / potential profit-taking' if lo > price else 'current-price area / confirmation needed')
        zones.append({'low':lo,'high':hi,'role':role,'families':families,'confluence':len(families),'evidence':[{'label':x['label'],'price':x['price']} for x in group]})
    if (d.volume.tail(20)==0).all(): warnings.append('Volume unavailable or zero over last 20 bars; VWMA and volume ratio unavailable')
    def scalar(v): return None if pd.isna(v) or not np.isfinite(v) else float(v)
    return {'as_of':str(d.index[-1].date()),'close':price,'indicators':{k:scalar(v) for k,v in last.items()},'swings':swings,'zone_tolerance':tol,'zones':zones,'warnings':warnings,'method':'Daily bars; confirmed pivots only; unvalidated heuristics, not orders.'}
