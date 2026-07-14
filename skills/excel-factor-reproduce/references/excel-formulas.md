# Locked 66 Excel 因子公式

基础约定：

- `MA(x,N)` = `x.rolling(N).mean()`
- `EMA(x,N)` = `x.ewm(span=N, adjust=False).mean()`
- `SMA(x,N,1)` = 文华/通达信式递推平滑：`(x + (N-1) * prev) / N`
- `SUM(x,N)` = `x.rolling(N).sum()`
- `MAX(x,N)` = `x.rolling(N).max()`
- `MIN(x,N)` = `x.rolling(N).min()`
- `REF(x,N)` = `x.shift(N)`
- `AMOUNT` 在当前期货数据中按 `close * volume` 复现

## 价格和趋势

| 列名 | xlsx 指标 | 公式 |
|---|---|---|
| `excel_ER_bull_power_20` | ER | `high - EMA(close,20)` |
| `excel_ER_bear_power_20` | ER | `low - EMA(close,20)` |
| `excel_TII_40_21` | TII | `100 * SUM(max(close-MA(close,40),0),21) / (SUM(max(dev,0),21)+SUM(max(-dev,0),21))` |
| `excel_TII_signal_9` | TII | `EMA(TII,9)` |
| `excel_PO_9_26` | PO | `(EMA(close,9)-EMA(close,26))/EMA(close,26)*100` |
| `excel_MADisplaced_20_10` | MADisplaced | `REF(MA(close,20),10)` |
| `excel_POS_100` | POS | `(PRICE-MIN(PRICE,100))/(MAX(PRICE,100)-MIN(PRICE,100))`, `PRICE=(close-REF(close,100))/REF(close,100)` |
| `excel_PAC_upper_20` | PAC | `SMA(high,20,1)` |
| `excel_PAC_lower_20` | PAC | `SMA(low,20,1)` |
| `excel_ZLMACD_20_100` | ZLMACD | `(2*EMA(close,20)-EMA(EMA(close,20),20)) - (2*EMA(close,100)-EMA(EMA(close,100),100))` |
| `excel_TMA_20` | TMA | `MA(MA(close,20),20)` |
| `excel_TYP` | TYP | `(close+high+low)/3` |
| `excel_TYPMA1_10` | TYP | `EMA(TYP,10)` |
| `excel_TYPMA2_30` | TYP | `EMA(TYP,30)` |
| `excel_VMA_20` | VMA | `MA((high+low+open+close)/4,20)` |
| `excel_WMA_20` | WMA | weighted MA of close, latest weight = 20 |
| `excel_HMA_high_20` | HMA | `MA(high,20)` |
| `excel_SROC_13_21` | SROC | `(EMA(close,13)-REF(EMA(close,13),21))/REF(EMA(close,13),21)` |
| `excel_EXPMA_12` | EXPMA | `EMA(close,12)` |
| `excel_EXPMA_50` | EXPMA | `EMA(close,50)` |
| `excel_DC_upper_20` | DC | `MAX(high,20)` |
| `excel_DC_lower_20` | DC | `MIN(low,20)` |
| `excel_DC_middle_20` | DC | `(DC_upper + DC_lower)/2` |
| `excel_VIDYA_10` | VIDYA | `VI*close + (1-VI)*REF(close,1)`, `VI=abs(close-REF(close,10))/SUM(abs(close-REF(close,1)),10)` |
| `excel_Qstick_20` | Qstick | `MA(close-open,20)` |
| `excel_DEMA_60` | DEMA | `2*EMA(close,60)-EMA(EMA(close,60),60)` |
| `excel_TRIX_20` | TRIX | `(EMA(EMA(EMA(close,20),20),20)-REF(...,1))/REF(...,1)` |
| `excel_WC_ema20` | WC | `EMA((high+low+2*close)/4,20)` |
| `excel_WC_ema40` | WC | `EMA((high+low+2*close)/4,40)` |
| `excel_TEMA_20` | TEMA | `3*EMA(close,20)-3*EMA(EMA(close,20),20)+EMA(EMA(EMA(close,20),20),20)` |
| `excel_TEMA_40` | TEMA | `3*EMA(close,40)-3*EMA(EMA(close,40),40)+EMA(EMA(EMA(close,40),40),40)` |

## 通道和波动

| 列名 | xlsx 指标 | 公式 |
|---|---|---|
| `excel_FB_upper_1_618` | FB | `MA(close,20)+1.618*MA(TR,20)` |
| `excel_FB_lower_1_618` | FB | `MA(close,20)-1.618*MA(TR,20)` |
| `excel_FB_upper_2_618` | FB | `MA(close,20)+2.618*MA(TR,20)` |
| `excel_FB_lower_2_618` | FB | `MA(close,20)-2.618*MA(TR,20)` |
| `excel_FB_upper_4_236` | FB | `MA(close,20)+4.236*MA(TR,20)` |
| `excel_FB_lower_4_236` | FB | `MA(close,20)-4.236*MA(TR,20)` |
| `excel_APZ_upper_10_20` | APZ | `EMA(EMA(close,20),20)+2*EMA(EMA(high-low,10),10)` |
| `excel_APZ_lower_10_20` | APZ | `EMA(EMA(close,20),20)-2*EMA(EMA(high-low,10),10)` |
| `excel_KC_upper_14_20` | KC | `EMA(close,20)+2*MA(TR,14)` |
| `excel_KC_lower_14_20` | KC | `EMA(close,20)-2*MA(TR,14)` |
| `excel_BOP_20` | BOP | `MA((close-open)/(high-low),20)` |
| `excel_ENV_upper_25_5pct` | ENV | `MA(close,25)*1.05` |
| `excel_ENV_lower_25_5pct` | ENV | `MA(close,25)*0.95` |
| `excel_HLMA_high_20` | HLMA | `MA(high,20)` |
| `excel_HLMA_low_20` | HLMA | `MA(low,20)` |

`TR=max(high-low, abs(high-REF(close,1)), abs(low-REF(close,1)))`。

## 摆动和位置

| 列名 | xlsx 指标 | 公式 |
|---|---|---|
| `excel_RSIH_40_120` | RSIH | `RSI - EMA(RSI,120)`, `RSI=SMA(up,40,1)/SMA(abs(diff),40,1)*100` |
| `excel_Demarker_20` | Demakder | `MA(Demax,20)/(MA(Demax,20)+MA(Demin,20))` |
| `excel_TSI_25_13` | TSI | `EMA(EMA(diff,25),13)/EMA(EMA(abs(diff),25),13)*100` |
| `excel_IMI_14` | IMI | `SUM(if(close>open,close-open,0),14)/(INC+DEC)` |
| `excel_CMO_20` | CMO | `(SUM(max(diff,0),20)-SUM(max(-diff,0),20))/(SUM(max(diff,0),20)+SUM(max(-diff,0),20))*100` |
| `excel_OSC_40` | OSC | `close - MA(close,40)` |
| `excel_OSCMA_20` | OSC | `MA(OSC,20)` |
| `excel_CLV` | CLV | `(2*close-low-high)/(high-low)` |
| `excel_CLVMA_60` | CLV | `MA(CLV,60)` |

## 成交量

| 列名 | xlsx 指标 | 公式 |
|---|---|---|
| `excel_PVO_12_26` | PVO | `(EMA(volume,12)-EMA(volume,26))/EMA(volume,26)` |
| `excel_BIASVOL_6` | BIASVOL | `(volume-MA(volume,6))/MA(volume,6)` |
| `excel_BIASVOL_12` | BIASVOL | `(volume-MA(volume,12))/MA(volume,12)` |
| `excel_BIASVOL_24` | BIASVOL | `(volume-MA(volume,24))/MA(volume,24)` |
| `excel_MACDVOL_20_40` | MACDVOL | `EMA(volume,20)-EMA(volume,40)` |
| `excel_MACDVOL_signal_10` | MACDVOL | `MA(MACDVOL,10)` |
| `excel_ROCVOL_80` | ROCVOL | `(volume-REF(volume,80))/REF(volume,80)` |
| `excel_VWAP_20` | VWAP | `SUM(volume*TYP,20)/SUM(volume,20)` |
| `excel_FI_13` | FI | `EMA((close-REF(close,1))*volume,13)` |
| `excel_MAAMT_40` | MAAMT | `MA(close*volume,40)` |
| `excel_SROCVOL_20_10` | SROCVOL | `(EMA(volume,20)-REF(EMA(volume,20),10))/REF(EMA(volume,20),10)` |

