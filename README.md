# 文档工具箱

文档工具箱用于处理 Word / PowerPoint 文档，主要面向这些场景：

- 把 Word 月报整理成 PPT 模板内容
- 对 Word / PPT 做脱敏，生成占位符和映射 JSON
- 把脱敏文档交给外部 AI 处理后，再按映射 JSON 还原
- 根据映射 JSON 生成给外部 AI 使用的安全 Prompt
- 检查版本并下载更新包

> 重要提示：本工具只能辅助处理文档，不能保证 100% 消除保密、隐私、商业秘密或合规风险。对外发送、上传第三方系统、交给外部 AI 或正式归档前，请务必人工复核。

## 支持格式

推荐格式：

- Word：`.docx`
- PowerPoint：`.pptx`

也支持旧格式：

- Word：`.doc`
- PowerPoint：`.ppt`

处理 `.doc` / `.ppt` 需要本机安装 LibreOffice。没有 LibreOffice 时，`.docx` / `.pptx` 仍可正常使用。

LibreOffice 安装示例：

```powershell
winget install --id TheDocumentFoundation.LibreOffice -e
```

## 第一次使用前

如果只使用 Release 里的客户端，不需要安装 Python，也不需要阅读源码。

建议准备：

- Windows 或 macOS 电脑
- Ollama，用于本地模型辅助识别和改写
- 一个本地模型，例如 `qwen2.5:7b-instruct-q4_K_M`

安装模型：

```powershell
ollama pull qwen2.5:7b-instruct-q4_K_M
```

如果不使用本地模型，脱敏候选识别仍可走规则模式，但更依赖人工审核。

## 基本流程

常见的外部 AI 协作流程：

1. 在 `脱敏` 页选择原始 Word / PPT。
2. 点击 `识别候选映射`。
3. 在右侧映射表里人工检查、删除误识别、补充漏识别。
4. 点击 `生成脱敏文档`，得到脱敏文件和映射 JSON。
5. 在 `AI Prompt` 页载入映射 JSON，生成给外部 AI 的 Prompt。
6. 把脱敏文档和可复制 Prompt 交给外部 AI。
7. 在 `还原` 页选择 AI 修改后的文件和映射 JSON，生成还原后的文档。
8. 人工复核最终文件。

## 月报转 PPT

在 `月报转 PPT` 页依次选择：

- 原始 Word 文件
- PPT 模板
- 输出 PPT 路径
- 本地模型

工具会尽量保持模板标题和版式；内容放不下时会自动续页。生成后仍建议人工检查页码、表格、标题和重点内容。

## 脱敏

在 `脱敏` 页依次选择：

- 原始文件
- 脱敏输出路径
- 最终映射 JSON 输出路径

推荐操作：

1. 点击 `识别候选映射`。
2. 逐项检查右侧映射表。
3. 删除明显误识别内容。
4. 手工补充漏掉的重要公司、项目、客户、人员等名称。
5. 点击 `生成脱敏文档`。

脱敏后会得到：

- 脱敏后的 Word / PPT
- 映射 JSON

映射 JSON 很重要，它保存了 `占位符 -> 原始敏感词` 的关系，本身也属于敏感文件。请和脱敏文档一起保存好。

占位符示例：

- `__COMPANY_001__`
- `__PERSON_003__`
- `__PROJECT_002__`

## AI Prompt

`AI Prompt` 页可以从映射 JSON 生成两块内容：

- `可复制给外部 AI 的 Prompt`
- `内部审核说明`

可复制 Prompt：

- 只包含占位符，不包含原始敏感词
- 会提醒外部 AI 不要新增、改写或删除占位符
- 会提示哪些占位符可能指向同一对象

内部审核说明：

- 只给自己看
- 会显示归组理由和原始名称线索
- 不建议发给外部 AI

不要把映射 JSON 或内部审核说明发给外部 AI，除非你确认其中内容可以外发。

## 还原

在 `还原` 页依次选择：

- AI 修改后的文件
- 映射 JSON
- 还原输出路径

还原规则：

- 文件里仍保留的占位符会被替换回原始敏感信息。
- 如果外部 AI 删除了整句内容，对应敏感信息不会凭空恢复。
- 如果外部 AI 轻微改坏占位符，例如 `COMPANY_001` 或 `__COMPANY-001__`，工具会尝试修复。
- 如果占位符损坏比较明显，工具会弹出确认窗口，让用户选择对应映射或直接输入原词。

确认窗口里可以：

- 选择某个映射项
- 直接输入要还原的原词
- 留空并保留原占位符
- 最后点击 `确认并还原`

还原完成后请检查运行日志。如果仍有未还原占位符，日志会列出 token，通常说明外部 AI 生成了映射表中不存在的新编号。

## 更新

客户端启动后会自动检查是否有新版本，也可以在 `关于` 页手动点击 `检测更新`。

检测到新版本后：

- 会下载对应系统的 Release 安装包。
- Windows exe 和 macOS app 的打包版本可在确认后自动替换旧版本并重启。
- 源码运行时只下载更新包，不会自动替换当前源码。

## 从源码运行

普通使用者建议直接下载 Release 客户端。只有本地调试或自行发布版本时，才需要看这一节。

准备：

- Python 3.10+
- Ollama（如果要使用本地模型）

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

启动 GUI：

```powershell
python gui_converter.py
```

运行测试：

```powershell
python -m unittest discover -s tests -v
```

当前测试覆盖 Prompt 生成、占位符修复、Word/PPT 脱敏还原、GUI 日志桥接、更新包选择、报告转换规则和架构边界。

## 构建客户端

安装构建依赖：

```powershell
python -m pip install -r requirements-build.txt
```

Windows 构建：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

macOS 构建：

```bash
bash scripts/build_macos.sh
```

构建产物会输出到 `dist` 目录。版本号优先读取当前 git tag；没有 tag 时使用开发版本号。

## 代码结构

主要入口：

- `gui_converter.py`：启动 GUI。
- `docx_to_ppt_converter.py`：月报转 PPT 命令行入口。
- `sanitize_docx.py`：脱敏/还原相关命令行入口。

GUI 模块：

- `gui_app/app.py`：主窗口、导航和页面组装。
- `gui_app/runtime.py`：后台任务、日志桥接、模型探测、文件打开等运行时能力。
- `gui_app/style.py`：主题和样式。
- `gui_app/widgets.py`：共用控件。
- `gui_app/sanitize/`：脱敏页 feature package，包含 layout、actions、table、mapping service。
- `gui_app/*_tab.py`：其他功能页；部分根级 `sanitize_*` 文件仅为兼容旧导入。

脱敏/还原模块：

- `doc_sanitizer/services/document_sanitizer.py`：对象化入口 `DocumentSanitizer`，负责 scan/sanitize/restore 工作流。
- `doc_sanitizer/engine.py`：稳定的函数 wrapper，兼容旧 API。
- `doc_sanitizer/scanning.py`：扫描文本、合并候选、生成映射 payload。
- `doc_sanitizer/mapping.py`：`MappingPayload`、`ReplacementItem`、映射 JSON 读写和编号规则。
- `doc_sanitizer/io/file_types.py`：支持格式和默认路径。
- `doc_sanitizer/io/text_collection.py`：DOC/PPT 可见文本和包内 XML 文本采集。
- `doc_sanitizer/io/replacement_engine.py`：脱敏/还原替换引擎，使用 `ReplacementDirection.SANITIZE / RESTORE` 表达方向。
- `doc_sanitizer/io/ooxml_package.py`：直接修改 OOXML 包内文本，补足 python-docx/python-pptx 覆盖不到的位置。
- `doc_sanitizer/io/operations.py`：文件级脱敏和还原操作。
- `doc_sanitizer/placeholders/parser.py`：占位符解析。
- `doc_sanitizer/placeholders/scoring.py`：损坏占位符相似度评分。
- `doc_sanitizer/placeholders/detection.py`：未知或损坏占位符检测。
- `doc_sanitizer/placeholders/repair.py`：占位符修复组合逻辑。
- `doc_sanitizer/prompt_builder.py`：外部 Prompt 和内部审核说明生成。
- `doc_sanitizer/fuzzy_mapping.py`、`doc_sanitizer/document_io.py` 和部分根级同名模块：兼容 facade，保留旧导入路径，不应继续增加业务逻辑。

报告转换模块：

- `report_converter/services/report_converter.py`：对象化入口 `ReportConverter`，负责 Word 到 PPT 转换工作流。
- `report_converter/engine.py`：函数式转换入口和内部渲染流程，兼容旧 API。
- `report_converter/parsing.py`：解析 Word 为 `ParsedReport`。
- `report_converter/models.py`：核心领域对象，例如 `ParsedReport`、`ReportSection`、`ReportParagraph`。
- `report_converter/drafting.py`：组织 slide draft。
- `report_converter/drafting_parts/source_selection.py`、`metrics.py`、`rules.py`、`text_cleanup.py`、`llm_client.py`：来源选择、指标提取、规则、文本清理和 LLM 调用。
- `report_converter/ppt/content_regions.py`、`formal_layout.py`、`pagination.py`、`slide_ops.py`、`table_fill.py`：PPT 布局、分页、页面操作和表格填充。
- `report_converter/layout.py`：兼容 facade，不应继续增加业务逻辑。

## 实现说明

### 脱敏

工具会先采集 Word / PPT 中的可见文本，并读取 OOXML 包中高层库可能漏掉的 XML 文本。随后使用规则和本地模型辅助识别公司、人员、项目、客户、金额等候选敏感项。

识别结果不会立刻写入文档，而是先进入映射表，用户审核后才会生成最终脱敏文档。

### 映射 JSON

映射 JSON 使用版本化结构，核心字段是 `entries`。每个条目包含：

- `placeholder`
- `original`
- `category`
- `enabled`
- `source`

代码内部使用 `MappingPayload` dataclass 表达映射 payload，同时保留 `payload["entries"]` 这类旧访问方式，兼容现有 GUI 和测试。

### 旧版 Office 格式

`.docx` / `.pptx` 会直接处理。`.doc` / `.ppt` 是旧版二进制格式，工具会调用 LibreOffice 临时转换成 `.docx` / `.pptx`，处理完成后再按需要转换回旧格式。

### Prompt 生成

工具会读取映射 JSON，找出可能指向同一对象的占位符组合，例如简称、全称、项目缩写等。生成给外部 AI 的 Prompt 时只输出占位符，不输出原始敏感词。

内部审核说明会展示归组理由和原始名称线索，只用于用户自己判断。

### 还原

还原时，工具会读取映射 JSON，把文件中仍存在的占位符替换回原始词。如果外部 AI 删除了整句内容，工具不会自动补回被删除的敏感词。

占位符修复分三层：

- 解析：把 `COMPANY_001`、`__COMPANY-001__` 等形式规范化。
- 评分：优先匹配编号，避免把 `PROJECT_015` 错还原成 `__PROJECT_005__`。
- 检测：发现映射表里不存在的新编号或粘连 token，并交给用户确认。

## 已知限制

- OCR、图片、复杂文本框和特殊版式仍可能需要人工复核。
- 英文合同、项目简称、客户简称更依赖人工确认。
- 同一对象归组基于规则和文本相似度，不能替代人工判断。
- 工具无法替代正式的数据安全、保密和合规审核流程。
