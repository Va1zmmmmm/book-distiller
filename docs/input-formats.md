# 输入、响应与出处

JSON 顶层为对象，UTF-8（允许 BOM）。输入不会被改写，输出必须是新目录。按 examples 的完整文件开始最省事。卡片 JSON 及 Markdown 可供下游可视化读取；首版不提供私人版平台导入器或消费项目兼容承诺。

## 读后卡片

输入：`book.title` 必填，author/edition/finishTime 可选字符串；review 字符串；highlights 为对象数组，每项 text 必填，location 可选用于读者回查。书评和划线至少有一项非空，合计不超过 120000 字，超限明确拒绝。

响应：core_claims 为 1–4 个非空字符串；claim_sources 数组逐条对应，每条是非空来源编号数组，review 指书评，h1/h2 指第 1/2 条划线。来源编号仅证明引用了存在的材料，不证明语义正确。

takeaway 可为 null；否则必须是带 `〔划线N〕` 的原句，或末尾标 `（概括）` 的概括，同时给 takeaway_sources。takeable 可为 null；非空时填 label、core、shape 和 takeable_sources；use 可选。shape 为 single、steps 或 items。steps 使用非空步骤数组，并给 steps_sources 逐步对应；items 每项使用 image 和 how 字符串。quote 可选，必须带 `〔划线N〕`。golden_quotes 最多 4 条带出处原句；anti_patterns 最多 2 条，links 最多 3 条，没有就空数组。模型提示词要求这些自由文本解释有材料依据，程序不宣称已自动验证其语义。

原句支持逐字连续摘录或 `[……]` 显式节略。节略前后各段必须依序存在于同一条划线，不能跨条拼接。references.json 给出字符偏移（0 起、右开）及行号（1 起），并记录输入副本与候选哈希。Markdown 明示候选状态。review 的 accept 认领全部观点和已有可带走内容，partial 明确指定认领项，reject 不认领；每次判断追加在 reviews/，不覆盖候选和历史。

## 整书准备

输入：id、title、edition 必填，author/genre 可选；chapters 为非空数组，按实际阅读顺序排列。每章 id、title、text 必填。id 只允许 1–64 个 ASCII 字母、数字、下划线或连字符，第一位须为字母或数字，不允许 Windows 设备保留名；章节 id 不得重复。edition 填译者、出版社/版本等你已确认的信息，程序不会自动认书或校勘。

原文按每片段至多 12000 字切开，优先换行边界，全部字符均保留。prepare 无模型响应时只准备原文；有响应时结构为 `{"chunks":{"c1-001":{...},...}}`。片段编号按章节 id + 三位序号生成（超过 999 仍支持）。响应必须覆盖且仅覆盖本次全部片段，不能拿旧章节编号凑数。

每片段响应：summary 非空且不超过 300 字；concepts 为 `{name, explain}` 数组；quotes 为最多 8 条逐字原句/显式节略。没有概念、引文就空数组。引文只在其对应片段内匹配，不拿别章同句放行。未分析的原文也可用于陪读。

输出 chapters/ 保留完整原文，analysis/ 为外部解释；manifest.json 记录源文本/响应文件哈希，quotes.json 记录逐条出处。它们是**全书准备端**，不要整包提供给未读完的陪读会话。更改原文、分析或引文后旧包会被拦截，应使用新输入、新目录重建，不手改哈希绕过。

## 笔记和阅读位置

session 的 chapter 是已读到的章节 id，不是希望 AI 帮你预读的目标。through-line 使用章节原文文件的 1 起行号，以 LF 换行为坐标（CRLF 也适用，Unicode 分隔符不另计行）；当前部分章摘要和笔记都暂不导出。未指定 through-line 表示已读完整章，包含此前全部章节。导出没有后章目录；文件名及标题仍来自你提供的章节，请先清除章节自身标题中的剧透。

note 输入只允许 chapter_id、reader、ai、questions、corrections。前两项为字符串，后两项为字符串数组。chapter_id 须存在且至少一项有内容。文件中的 reader/ai 身份由填写者负责，程序不会把 AI 观察转成读者观点。每次创建独立事件并按 recorded_at 导出，不修改既有记录。
