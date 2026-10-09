# BookDistiller

把读完一本书留下的书评与划线整理成可回看的卡片；把自己提供的整书章节准备成有出处、按阅读位置导出的陪读材料。

卡片服务于回看自己的阅读，也方便别人从你的视角认识一本书。它可以停在意象、感受或未解问题上，不要求每本书都提供方法。整书资料保留原文，帮助陪读时回到书中的具体段落。

首版是本地命令行工具，Python 3.11+，运行时只用标准库。默认不联网，不需要读书平台账号。输入为 UTF-8 JSON；EPUB/PDF 解析、可视化和朋友圈图片排版尚未包含。原私人版的全书人格/主题 reduce 与客户端技能安装没有搬入首版；这里提供逐片段导航、全量原文准备和陪读导出。

## 五分钟离线演示

在本仓库根目录执行。输出目录必须尚不存在。

```sh
python -m book_distiller card examples/card-fiction-input.json --response examples/card-fiction-response.json --out output/card-fiction
python -m book_distiller card examples/card-method-input.json --response examples/card-method-response.json --out output/card-method
python -m book_distiller review output/card-method --decision partial --accept-claim 1 --accept-takeable --note "愿意尝试，但保留对效果的判断"
python -m book_distiller prepare examples/book-input.json --response examples/book-response.json --out output/book
python -m book_distiller note output/book --event examples/note-event.json
python -m book_distiller session output/book --chapter c1 --out output/read-c1
```

打开 `output/card-fiction/card.md`：有依据的未解问题和原句保留，“可带走的东西”留空。`card-method/card.md` 保留材料中的三步方法。每张卡都有机器可读 JSON、原输入副本和引文核验坐标；候选默认未经读者确认，review 只追加接受/部分接受/拒绝记录。

`output/book` 是准备端，含全书材料。陪读时只提供 `output/read-c1` 给模型，并按 `START.md` 开始；它不含后章标题、原文或分析。只读了当前章一部分时加 `--through-line N`，N 对应生成的章节原文文件行号；部分章不导出该章的摘要或既有笔记。没有模型响应也能 `prepare` 原文，去掉 `--response` 即可。

示例全为新编、虚构内容，响应为预先编排的演示 JSON。上述命令验证流程，不代表真实模型生成质量或陪读效果。

## 使用自己的材料和模型

先按 [输入格式](docs/input-formats.md) 准备 JSON，并确认自己可以使用这些材料。把输入和输出放在仓库外或 `private/`、`output/`；不提交私人材料。

复制 `provider.example.json` 为 `provider.local.json`，填写自己的 HTTPS Chat Completions 兼容接口和模型名。密钥只从配置指定的环境变量读取，不填进 JSON：

```powershell
# 在当前 PowerShell 会话里从安全存储设置 BOOK_DISTILLER_API_KEY；不要把密钥写入仓库或命令历史。
python -m book_distiller card private/card-input.json --online --config provider.local.json --out output/my-card
python -m book_distiller prepare private/book-input.json --online --config provider.local.json --cache-dir cache/book --out output/my-book
```

只有显式 `--online` 才请求服务。卡片发送书评与划线；整书按不超过 12000 字的片段逐个发送，不静默丢弃长章尾部。实际费用、上下文限制、JSON 能力和数据政策取决于你选择的服务；当前版本未承诺任何提供商兼容性。默认没有缓存；可选缓存会保存响应正文，复用时仍按当前原文核验引文。失败不自动重试，不覆盖既有输出；IO 失败可能留下不完整的新目录，保留检查后用另一个新目录重跑。

可以安装为 CLI（构建安装工具可能需要下载，运行本身无第三方依赖）：

```sh
python -m pip install .
book-distiller --help
```

## 核验与边界

引文须匹配指定划线/章节片段，显式节略用 `[……]`。核验不做标点归一或模糊匹配。来源编号存在、字面回源通过，都不能证明模型解释成立，仍需读者逐条判断。

按阅读位置导出可以限制提供给模型的材料，无法控制它的训练记忆，也不能保证提示词完全阻止剧透或错误解释。首版不自动聊天、不自动推进阅读、不写入任何模型客户端配置。

运行 `python -m unittest discover -s tests -v` 验证离线契约和本机模拟服务；`python tools/check_release.py` 检查公共目录文件清单及常见泄漏形状。

继续阅读：[陪读流程](docs/companion.md)、[真实模型小样本](docs/live-checks.md)、[隐私](PRIVACY.md)、[安全](SECURITY.md)、[贡献](CONTRIBUTING.md)、[来源与许可](NOTICE.md)。代码和新编示例采用 [MIT License](LICENSE)。
