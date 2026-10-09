# 贡献

先用 README 的虚构示例复现，提交问题时标明 Python、系统、命令和预期行为。不要上传真实书籍全文、账号数据、API 密钥或私人笔记。复制示例创建新的 output 目录，避免覆盖人工产物。

运行：

```sh
python -m unittest discover -s tests -v
python tools/check_release.py
```

发布检查针对清洁副本：它会拒绝清单之外的文件（包括 output、.venv、build 和安装产生的 egg-info），不会因为它们被 gitignore 忽略就放行。开发目录有这些产物时，按 tools/release-files.json 逐项复制到新的发布目录，再用 `python tools/check_release.py --root <发布目录>` 检查；Git 历史还需另行检查。

修改引文处理需覆盖：错章节/错划线、标点差异、未标节略和重复句。修改 session 需证明后章标题、原文、摘要、引文和笔记没有泄漏，部分章不带完整摘要。不要用模拟服务通过来宣称真实提供商或内容质量通过。

提交新的公开文件时更新 tools/release-files.json，逐个说明来源和许可，再扫描打包内容。清单防止误带文件，不代替人工判断内容版权。贡献默认按本项目 MIT 许可提交；引入外部代码保留其版权、许可及出处。路线图见 docs/companion.md。
