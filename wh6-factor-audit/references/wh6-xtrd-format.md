# WH6 XTRD 格式

已核实 WH6 公式文件夹中的 `.XTRD` 文件是兼容 GB18030 的文本文件，内部有类似 XML 的分段。审计工具重点关注：

- `<PARAM>`：零行或多行默认参数，例如 `[N,1.000000,100.000000,14.000000]`。
- `<CODE>`：公式语句，以及绘图/样式语句。
- `<DESCRIPTION>`、`<VERSION>`、`<EDITTIME>`、`<PROPERTY>`、`<BRIEFDESCRIPTION>` 等其他分段属于来源元数据，不作为 locked 审计的计算输入。

locked 合同中见到的输出形式：

- 显式命名输出：`K:SMA(RSV,M1,1);`
- 内部赋值：`RSV:=...;`，本身不导出。
- 匿名表达式输出：`CLOSE-REF(MA(CLOSE,20),11);`
- 带样式装饰的输出：`2*(DIFF-DEA),COLORSTICK;`
- 清洗名或 hash 名输出：中文名、重复名等被映射成稳定的 `wh6_...` 列名。

对这个 skill 来说，`.XTRD` 是 locked 198 列的来源证据。skill 不会自动纳入额外 `.XTRD` 文件。
