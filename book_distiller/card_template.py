"""Adapted from the project card prompt and Markdown renderer; no account adapters."""
import re

CARD_PROMPT = '你是书籍蒸馏师。把下面这本书的「读者书评 + 划线笔记」蒸馏成一张卡片。\n目标是：几个月后读者翻到这张卡，能想起**自己**读这本书时留下了什么——有依据的发现、划下的原句、还没弄懂的地方。禁止泛泛而谈、禁止教科书味。\n\n先判断材料支持什么，再决定写什么：\n- 书评是读者自己的话，第一顺位依据；划线是第二顺位。两者都不支持的结论、步骤、效果，不要写进卡里。\n- 书评若明示含转贴、引用或模型整理，要区分来源；不能把附带的模型解释当成读者已经认领的理解。\n- 允许停在发现、意象、感受或问题上：「怎么用」可以省略，「可带走的东西」整节也可以为 null。**材料不足就留空，不要为了填栏硬找用途。**\n- 保留犹疑、矛盾、绝望、尚未理解的状态；不要统一转成积极自助建议，也不要替读者完成结论。\n- 小说人物或叙述者的一句话，不等于作者主张，也不等于普遍生活处方；没有依据就不编操作步骤、预期效果或必然结果。\n- 材料里确实有的方法（方法书、心理书、读书方法等）要保留具体步骤和读者自己谈到的用途，不要为了"避免说教"把实用性删光。\n- 分清「材料里已有的发现」和「你延伸的联想」：延伸只在确有价值时作为可选内容，语气与证据相称，不要靠堆"也许"掩饰牵强。\n- 模型额外提出的用法，在 use 开头标「可选延伸」或「可选写作联想」；读者自己明确谈过的应用可直接保留，不强制每张卡提供延伸。\n- 命名尽量具体、朴素：不许为每本书新造"检验器""透镜""装置"这类工具名；书里本来有的意象和术语可以保留。\n\n「可带走的东西」：这本书最能让读者带走的一样东西。用**两层**描述：\n- label（语义名，自由但必须具体）：最贴的具体语义名，如"回信前先复述问题""街角的空椅子"。**禁止用形态名（意象装置/框架/立场/技法）当 label**——那是 shape 管的事。label 是给人筛选/识别的，要能一眼看出这本书的可带走物具体是什么，宁可用书里原意象/原词，也不要泛。\n- shape（渲染形状，必选其一）：single（单段发现/立场/意象/问题）｜steps（材料支持的有序步骤）｜items（一组"具体名词：说明"并列条目）\n  判据：材料给出操作步骤→steps；是一组并列的具体名词（意象/术语/物件）+ 各自说明→items；是单段发现/立场/意象/问题→single\n\n只输出 JSON（不要输出其他文字），结构固定：\n{{"core_claims":["核心观点，按材料实际给1-4条，一句话一条；只有一个发现就只写一条，不凑数量。来自书评或划线，保留原术语；读者还没弄懂的照实写成未解，不补成结论"],\n"takeaway":"一句能带走的话（选填）：优先从划线中挑原文，原样引用并标〔划线N〕；材料足够才可概括并标注（概括）。没有合适内容就填 null，禁止为填栏造一句话",\n"takeable":{{"label":"语义名","shape":"single|steps|items","core":"一句能带走的核心（必填）","use":"它怎么用（选填：材料或书评明确支持时才写，2-3句；写不出材料支持的用法就填 null，不要编）","steps":["步骤1","步骤2"],"items":[{{"image":"意象/名词","how":"说明或用法"}}],"quote":"可引用的原句（带〔划线N〕）"}},\n"golden_quotes":["金句：按实际可引用材料给0-4条原文，末尾标〔划线N〕，不要重复 takeaway；只有一条就给一条，没有就空数组，不凑数量"],\n"anti_patterns":["书里明确警告的陷阱/反模式，0-2条，没有就空数组"],\n"links":["关联记录，0-3条：优先从书评中读者自己提到的关联/思考线索提取（如明确提到某本书、某个关心的话题、某个反复出现的个人主题）。每条写明关联对象 + 一句话说明。书评和划线里没有明确关联就空数组，禁止编造"]}}\n规则：\n- shape 决定内容字段：shape=steps 填 steps 数组（items 留空）、shape=items 填 items 数组（steps 留空）、shape=single 两者都留空\n- takeable 非 null 时 core 必填；use 选填（没有依据就 null，不要用通用生活建议凑数）；quote 有原句就填，没有就留空\n- steps 必须有材料依据；材料只给出一段文学片段、没有可执行方法时，不要把它拆成步骤\n- 材料不支持独立的可带走内容→ takeable 填 null；任何类型的书都允许，不许硬造\n- core_claims 至少一条有依据的内容或未解问题；takeaway 可为 null，golden_quotes 可为空，takeable 可为 null\n\n书评（读者读完后的完整感受）：\n{review}\n\n划线笔记（编号对应）：\n{highlights}'

def render_md(meta: dict, card: dict, highlights: list[str]) -> str:
    lines = [f"# 🧪 蒸馏卡：《{meta['title']}》", ""]
    hdr = [f"- **作者**：{meta['author']}"]
    if meta.get("finishTime"):
        hdr.append(f"- **读完时间**：{meta['finishTime']}")
    hdr.append(f"- **笔记**：{meta.get('notes_total')} 条（划线 {len(highlights)}）")
    if meta.get("affection"):
        hdr.append(f"- **喜爱度**：{meta['affection']}")
    lines += hdr + ["", "## 核心观点", ""]
    lines += [f"- {c}" for c in (card.get("core_claims") or [])] + [""]
    takeaway = str(card.get("takeaway") or "").strip()
    if takeaway:
        lines += ["## 一句能带走的话", "", f"> {takeaway}", ""]

    # 「可带走的东西」按 shape 渲染（卡片契约：label 语义 / shape 渲染形状）
    tk = card.get("takeable")
    if isinstance(tk, dict) and (tk.get("shape") or tk.get("core") or tk.get("label")):
        shape = str(tk.get("shape") or "single").strip().lower()
        if shape not in ("single", "steps", "items"):
            shape = "single"
        label = str(tk.get("label") or "").strip()
        header = f"> shape: {shape}"
        if label:
            header += f" ｜ label: {label}"
        lines += ["## 可带走的东西", header, ""]
        if tk.get("core"):
            lines += [f"**{tk['core']}**", ""]
        if tk.get("use"):
            lines += [f"- **怎么用**：{tk['use']}"]
        if shape == "steps":
            k = 0
            for s in (tk.get("steps") or []):
                # 2026-10-08：模型有时把「1. 」写进步骤文本，避免渲染成「1. 1. …」
                s = re.sub(r"^\d+[.、]\s*", "", str(s).strip())
                if s:
                    k += 1
                    lines += [f"{k}. {s}"]
        elif shape == "items":
            for it in (tk.get("items") or []):
                if isinstance(it, dict) and (it.get("image") or it.get("how")):
                    lines.append(f"- **{it.get('image', '')}**：{it.get('how', '')}")
        if tk.get("quote"):
            lines += [f"- **原句**：{tk['quote']}"]
        if lines[-1] != "":       # 2026-10-08：use/quote 都可能缺省，别留连空行
            lines += [""]

    golden_quotes = card.get("golden_quotes") or []
    if golden_quotes:
        lines += ["## 金句", ""]
        lines += [f"- {q}" for q in golden_quotes] + [""]
    ap = card.get("anti_patterns") or []
    if ap:
        lines += ["## 反模式/陷阱", ""]
        lines += [f"- {a}" for a in ap] + [""]
    return "\n".join(lines).rstrip() + "\n"
