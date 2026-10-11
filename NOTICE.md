# 来源与许可

本目录自行编写的代码、文档和 examples 中的新编示例按 MIT License 提供。示例由 AI 辅助新编，使用虚构内容，不来自真实读者书评、商业书籍或私人阅读记录。响应 JSON 是人工编排的演示候选，用于重现管线，不是模型效果测评样本。第三方文件采用各自许可，见下文。

读后卡片提示词与 Markdown 渲染器、严格引文坐标检查、陪读约定整理自本项目此前自行维护的实现。此独立版新建标准 JSON 输入、按阅读位置导出和显式模型适配层；没有包含原工作库的账号接入、凭据工具或私人材料。

早期私人项目曾使用 [virgiliojr94/book-to-skill](https://github.com/virgiliojr94/book-to-skill) 的 MIT 解析器（commit 29991b2，Copyright 2025 virgiliojr94），也受到其书籍转资料工作流的启发。本公开目录没有复制该解析器或其文件，不宣称上游解析能力为本项目原创；未来若引入，须保留其许可和署名。

软件许可不授予输入书籍、译文、划线摘录或第三方图片的使用权。自行导入的材料不自动成为本仓库的公开数据，分享前需单独判断来源和授权。首版没有附带书籍下载器、商业书全文或真实个人书库。

v0.2.0 网页内置 [fflate 0.8.3](https://github.com/101arrowz/fflate)（MIT，Copyright Arjun Barrett）和 [PDF.js / pdfjs-dist 6.4.299](https://github.com/mozilla/pdf.js)（Apache-2.0，Mozilla Foundation）。原许可分别保存在 web/vendor/fflate-LICENSE.txt 与 pdfjs-LICENSE.txt；文件未修改，版本、来源和 SHA256 在 web/vendor/manifest.json。浏览器导入器与排版界面为本项目新增；未引入早期 book-to-skill 解析器。提取结果仍需人工核对，字体和多栏等特殊情况不保证无误。

可选浏览器 AI 请求依据 [DeepSeek 官方 Chat Completions 文档](https://api-docs.deepseek.com/api/create-chat-completion/)（2026-10-11 核对）。旧模型名仍由官方兼容，但不保证所有网络环境直连可用；提示词下载与结果导入不依赖此服务。
