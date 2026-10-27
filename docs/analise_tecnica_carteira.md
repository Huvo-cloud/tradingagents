# Análise técnica reutilizável para TradingAgents

Módulo apenas de análise: não liga a corretores nem executa ordens. Python >=3.10; dependências `pandas`, `numpy` e, para dados online, `yfinance` (já constam direta ou transitivamente do projeto). O adaptador exige também `langchain-core`.

## Execução

Na raiz do repositório, instalar as dependências do projeto segundo o README principal e executar:

```bash
python -m unittest discover -s tests/portfolio_technical -v
python -m cli.main
```

Selecionar a opção de dados online, o analista de mercado, a data e uma ação (por exemplo EDPR.LS, BCP.LS, AAPL ou ARR). O analista é instruído a chamar a ferramenta de análise técnica; essa chamada depende do modelo e pode não ocorrer. Verificar no relatório as âncoras e os níveis, ou chamar diretamente:

```python
from tradingagents.dataflows.tradingagents_tool import get_portfolio_technical_report
print(get_portfolio_technical_report.invoke({"symbol": "EDPR.LS", "as_of": "2024-03-08"}))
```

A data é inclusiva. O Yahoo pode não disponibilizar dados de um símbolo ou período e o programa indicará o erro; não há garantia de dados atualizados, cobertura ou moeda. Verificar sempre o último fecho, a bolsa e a disponibilidade de volume. Uma vela diária durante a sessão pode estar incompleta. A análise não usa posição nem caixa: a interpretação de recompra depende da carteira, sem pressupor liquidez disponível.

## Metodologia

- SMA20/50/200 requerem 20/50/200 fechos. RSI14 e ATR14 usam Wilder com semente média simples; MACD usa EMA 12/26 e sinal EMA9 (`adjust=False`); VWMA20 usa volume de 20 sessões; volume relativo compara com a média de 20 sessões incluindo a atual; volatilidade histórica é o desvio padrão amostral dos retornos diários em 20 sessões, anualizado por √252.
- Horizontes são janelas móveis de 63, 126 e 252 **sessões diárias**, não velas semanais ou mensais. Um pivô é máximo/mínimo estrito relativamente a 3 sessões de cada lado, só confirmado após as 3 seguintes. Patamares e velas simultaneamente máximas e mínimas são ignorados. Em cada janela escolhe-se o pivô confirmado mais recente e o pivô oposto válido mais próximo anterior. Não se selecionam extremos globais; não há movimento válido quando não existem pivôs suficientes. Os pivôs e datas são devolvidos para auditoria.
- Para um movimento A→B, os retraçamentos são `B − sinal × |B−A| × r`, r = 0,236; 0,382; 0,5; 0,618; 0,786. As extensões são `A + sinal × |B−A| × r`, r = 1,272 e 1,618; são projeções de amplitude, não extensões de três pontos. `0,5` é incluído como nível convencional, embora não seja um rácio de Fibonacci.
- Níveis positivos de retração/extensão, até seis pivôs recentes por horizonte e SMA disponíveis são agrupados por ordem crescente. A amplitude de cada grupo não excede o maior de 0,5 ATR14 ou 0,5% do preço. O grupo não é alargado artificialmente para a tolerância. A confluência conta famílias distintas: Fibonacci, pivôs, SMA20, SMA50, SMA200; vários níveis Fibonacci não contam como várias confirmações independentes. Os níveis individuais ficam visíveis em `evidence`.
- Zona integralmente abaixo/acima do último fecho é identificada como potencial suporte/resistência; uma zona que contém o preço exige confirmação. A classificação é geométrica, não valida força, reversão nem rentabilidade. RSI, MACD, volume e volatilidade são apresentados como contexto, não como níveis de preço nem votos de confluência. Uma resistência pode transformar-se em suporte após rutura; verificar reação, tendência, liquidez e risco. As regras são heurísticas não calibradas nem validadas como estratégia. Não calculam posição, stop, custos, impostos ou probabilidade.
- Preços Yahoo `auto_adjust=False` são geralmente ajustados para splits, mas não dividendos; confirmar a convenção e descontinuidades junto do fornecedor. Dividendos podem criar saltos e alterar indicadores; não misturar fechos ajustados com máximos/mínimos não ajustados. `Volume=0` é aceite para dias sem negócios; 20 dias com volume zero produzem aviso e VWMA indisponível. Não se fabricam dados ou SMA200 em histórico insuficiente.

## Integração

A ferramenta está registada no `Toolkit` e no `ToolNode` de mercado. O analista recebe a ferramenta e instruções para a chamar apenas em `online_tools=True`. É a mesma implementação que `analyze(df, as_of=...)` em `tradingagents/dataflows/technical.py`: o índice deve ser `DatetimeIndex` crescente único, com colunas Open, High, Low, Close e Volume. Os dados devem estar disponíveis na data da análise; reajustes retroativos podem causar viés. O modo offline mantém o comportamento existente e não usa a ferramenta. O cálculo não executa transações.

## Testes e fonte

`tests/data/aapl.csv` é uma cópia do ficheiro histórico público [msabid/stock_data](https://github.com/msabid/stock_data/blob/main/aapl_ticker.csv), SHA Git `ebc2e5fc1bdfae9477c509cba96d69e481764412`. O fornecedor descreve AAPL 2020–2024, mas o CSV não tem datas; os testes atribuem um índice artificial apenas para ordenar linhas. Não serve para inferir datas efetivas ou testar feriados. Restantes testes usam séries artificiais e verificam fórmulas, ausência de acesso a dados posteriores, tratamento de volume e coerência de zonas. Não foi efetuado backtest de rentabilidade nem uma execução real de EDPR/BCP. O aviso de licença MIT original está em `tests/portfolio_technical/data/LICENSE-aapl.txt`.
