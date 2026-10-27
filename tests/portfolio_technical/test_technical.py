import sys, unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tradingagents.dataflows.technical import analyze, indicators, swing, validate, Config

class TechnicalTests(unittest.TestCase):
    def data(self, values):
        c=np.array(values,dtype=float); return pd.DataFrame({'Open':c,'High':c+1,'Low':c-1,'Close':c,'Volume':np.full(len(c),100)},index=pd.date_range('2020-01-01',periods=len(c)))
    def test_wilder_and_sma(self):
        x=indicators(validate(self.data(np.arange(10,260))))
        self.assertAlmostEqual(x.sma20.iloc[-1],249.5)
        self.assertAlmostEqual(x.rsi14.iloc[-1],100)
        self.assertAlmostEqual(x.atr14.iloc[-1],2)
        self.assertAlmostEqual(x.vwma20.iloc[-1],249.5)
    def test_fibonacci_pivot_and_no_lookahead(self):
        a=self.data([10]*35+[11,12,15,20,15,12,11,12,13,12,11,12,13,14,15,14,13,12,11,12,13,12,11,10,11,12,13,12,11,12,13,14,15,14,13,12,11,12,13,12])
        cut=a.index[-8]; r=analyze(a,as_of=cut,config=Config(pivot_window=2)); s=analyze(a.loc[:cut],config=Config(pivot_window=2))
        self.assertEqual(r,s)
        for z in r['zones']:
            self.assertLessEqual(z['high']-z['low'],r['zone_tolerance']+1e-10)
        for sw in r['swings'].values():
            if sw: self.assertLessEqual(pd.Timestamp(sw['end']['date']),cut-pd.Timedelta(days=2))
    def test_missing_and_flat_volume(self):
        a=self.data(np.full(220,10.)); a['Volume']=0
        r=analyze(a); self.assertIsNone(r['indicators']['vwma20']); self.assertEqual(r['indicators']['rsi14'],50)
        self.assertTrue(any('Volume' in w for w in r['warnings']))
        a.iloc[0,a.columns.get_loc('Close')]=np.nan
        with self.assertRaises(ValueError): analyze(a)
    def test_real_historical_aapl(self):
        # Source has no dates; a synthetic index is used solely for ordering, not market dates.
        path=Path(__file__).parent/'data'/'aapl.csv'; a=pd.read_csv(path); a.index=pd.date_range('2000-01-01',periods=len(a),freq='B')
        r=analyze(a); self.assertEqual(r['close'],float(a.Close.iloc[-1])); self.assertTrue(r['zones']); self.assertIsNotNone(r['indicators']['sma200'])
        self.assertAlmostEqual(r['indicators']['sma20'],a.Close.tail(20).mean())
        for zone in r['zones']: self.assertEqual(zone['confluence'],len(set(zone['families'])))
if __name__=='__main__': unittest.main()
