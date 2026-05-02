# 文件工具箱

把法务月报 `Word(.doc/.docx)` 转成模板 `PPT(.ppt/.pptx)`，并支持 `Word / PPT` 的脱敏与还原。

当前包含 3 个主要功能：
- `月报转 PPT`：把月报 Word 填进固定 PPT 模板
- `文档脱敏`：把敏感词替换成占位符，方便交给外部 AI 继续处理
- `文档还原`：把占位符恢复成原始敏感词

当前原生处理 `.docx` / `.pptx`。`.doc` / `.ppt` 属于旧版二进制 Office 格式，程序会通过 LibreOffice 先临时转换为 `.docx` / `.pptx` 再处理。

如果需要处理 `.doc` / `.ppt`，请先安装 LibreOffice：
- Windows：`winget install --id TheDocumentFoundation.LibreOffice -e`
- macOS：`brew install --cask libreoffice`
- 官网下载：[LibreOffice](https://www.libreoffice.org/download/download-libreoffice/)

如果当前环境没有 LibreOffice，仍然可以稳定处理 `.docx` / `.pptx`。

## 重要提示与免责声明

本工具用于辅助法务月报整理、文档脱敏和文档还原，不能替代人工合规审核。由于源文件格式、图片 OCR、规则识别、本地模型识别、外部 AI 改写和人工编辑都可能产生遗漏、误判或占位符损坏，本工具无法保证 100% 去除数据保密、隐私保护、商业秘密或其他合规风险。

对外发送、上传至第三方系统、交给外部 AI 处理或正式归档前，请务必由业务/法务/合规人员进行人工复核。使用者应自行判断输出文件是否符合所在组织的数据安全、保密和合规要求。

## 快速选择

### 我是直接下载 Release 的用户

你需要准备：
- Windows 或 macOS
- [Ollama](https://ollama.com/download)
- 至少一个本地模型，例如：

```powershell
ollama pull qwen2.5:7b-instruct-q4_K_M
```

你**不需要**准备：
- Python
- `pip`
- 源码运行依赖
- 打包依赖

直接下载 Release 里的可执行文件后运行即可。

### 我是从源码运行 / 开发的用户

你需要准备：
- Python `3.10+`
- `pip`
- [Ollama](https://ollama.com/download)（如果要启用本地模型）
- 本仓库源码

安装运行依赖：

```powershell
python -m pip install -r .\requirements.txt
```

如果还要本地打包，再安装：

```powershell
python -m pip install -r .\requirements-build.txt
```

## Prerequisites

### 1. Ollama

如果你要使用：
- 月报转 PPT 的模型改写
- 脱敏页的本地模型辅助识别

就需要安装并启动 `Ollama`。

下载：
- [Ollama 官网](https://ollama.com/download)

安装后确认：

```powershell
ollama list
```

### 2. 模型目录不是默认路径时

如果你的模型在自定义目录，例如 `D:\Ollama\models`，需要设置：

```powershell
[Environment]::SetEnvironmentVariable('OLLAMA_MODELS', 'D:\Ollama\models', 'User')
```

然后完全重启 Ollama。

### 3. 推荐模型

至少准备一个：

```powershell
ollama pull qwen2.5:7b-instruct-q4_K_M
```

如果机器配置更高，也可以使用：

```powershell
ollama pull qwen2.5:14b-instruct-q4_K_M
```

## 启动 GUI

源码运行：

```powershell
python .\gui_converter.py
```

按指定窗口尺寸模拟：

```powershell
python .\gui_converter.py --geometry 1366x768
python .\gui_converter.py --geometry 1440x900
```

GUI 当前包含 4 个页签：
- `月报转 PPT`
- `脱敏`
- `还原`
- `关于`

启动后会自动静默检测 GitHub Release 是否有新版本；也可以在 `关于` 页签里手动点击 `检测更新`。检测到新版本时，程序会打开 Release 下载页面，不会直接覆盖正在运行的客户端。

## 月报转 PPT

### GUI 用法

在 `月报转 PPT` 页签中填写：
- 原始 `docx`
- 模板 `pptx`
- 输出 `pptx`
- 模型名

然后点击“开始转换”。

### CLI 用法

```powershell
python .\docx_to_ppt_converter.py `
  --docx "C:\input.docx" `
  --template "C:\template.pptx" `
  --output "C:\output.pptx" `
  --model "qwen2.5:14b-instruct-q4_K_M" `
  --layout-mode formal `
  --theme formal_blue `
  --diversity none `
  --seed 7
```

### 常用参数

- `--ollama-url`：默认 `http://127.0.0.1:11434`
- `--timeout`：默认 `180`
- `--retries`：默认 `2`
- `--no-llm`：关闭模型，只用规则模式
- `--layout-mode`：`classic` / `formal`
- `--theme`：`formal_blue` / `corporate_gray` / `legal_red`
- `--diversity`：`none` / `low` / `medium` / `high`
- `--seed`：固定版式随机种子

### 当前行为

- 保持模板标题不变
- 只向内容区写入要点
- 放不下时自动续页
- 有表格时尽量避让表格区域
- 模型失败时回退规则模式

## 文档脱敏

当前支持：
- `doc`
- `docx`
- `ppt`
- `pptx`

输出包括两部分：
- 脱敏后的文件
- 映射文件 `json`

占位符示例：
- `__COMPANY_001__`
- `__PERSON_003__`
- `__PROJECT_002__`

### GUI 脱敏流程

推荐流程：
1. 选择原始文件
2. 点击“识别候选映射”
3. 在右侧映射表里人工审核
4. 点击“生成脱敏文档”

映射表支持：
- 搜索某个词是否已被识别
- 双击直接编辑 `类别 / 敏感词 / 替换为`
- 启用或禁用选中项
- 删除误识别项
- 手工新增映射
- 批量新增映射
- 载入旧的映射 `JSON` 继续审核

### CLI 脱敏

```powershell
python .\sanitize_docx.py sanitize `
  --input "C:\input.docx" `
  --output "C:\input_脱敏.docx" `
  --mapping "C:\input_映射.json"
```

脱敏 `pptx` 同理：

```powershell
python .\sanitize_docx.py sanitize `
  --input "C:\input.pptx" `
  --output "C:\input_脱敏.pptx" `
  --mapping "C:\input_映射.json"
```

### AI 辅助识别

CLI、GUI 和程序接口默认都会启用本地 Ollama 辅助识别：

```powershell
python .\sanitize_docx.py sanitize `
  --input "C:\input.docx" `
  --output "C:\input_脱敏.docx" `
  --mapping "C:\input_映射.json" `
  --model "qwen2.5:7b-instruct-q4_K_M"
```

旧版 `.doc` / `.ppt` 也可以作为输入或输出；如果当前环境无法转换，程序会提示安装 LibreOffice。

如果要关闭模型，只用规则：

```powershell
python .\sanitize_docx.py sanitize `
  --input "C:\input.docx" `
  --output "C:\input_脱敏.docx" `
  --mapping "C:\input_映射.json" `
  --no-llm-assist
```

### 发给外部 AI 的使用规则

你可以：
- 删除不需要的句子或段落
- 改写内容

你不应该：
- 修改占位符本身
- 拆分占位符
- 翻译占位符
- 加空格或改编号

也就是说：
- 如果某个敏感对象被保留，对应占位符必须原样保留
- 如果整句被删掉，占位符也可以一起删掉
- 被删掉的占位符不会在后续还原时凭空恢复

## 文档还原

当前支持：
- `doc`
- `docx`
- `ppt`
- `pptx`

### GUI 用法

在 `还原` 页签中填写：
- AI 修改后的文件
- 映射 `json`
- 输出文件路径

然后点击“开始还原”。

### CLI 用法

```powershell
python .\sanitize_docx.py restore `
  --input "C:\input_脱敏_AI修改后.docx" `
  --output "C:\input_还原.docx" `
  --mapping "C:\input_映射.json"
```

还原 `pptx` 同理：

```powershell
python .\sanitize_docx.py restore `
  --input "C:\input_脱敏_AI修改后.pptx" `
  --output "C:\input_还原.pptx" `
  --mapping "C:\input_映射.json"
```

## 推荐实战流程

### 流程 1：月报直接转 PPT

1. 原始月报 `docx`
2. 直接转成模板 `pptx`
3. 人工审核 PPT

### 流程 2：敏感月报外发处理

1. 原始月报 `docx` 先脱敏
2. 用脱敏后的 `docx` 去转 PPT，或发给外部 AI
3. 对最终 `word/ppt` 再做还原

当前已经实测跑通：
- `Word 脱敏 -> 脱敏 Word 转 PPT -> 对生成 PPT 还原`

需要注意：
- 只有最终文件中仍然保留的占位符，才会被还原
- 如果外部 AI 把某段内容整段删掉，对应敏感词不会被重新补回

## 打包

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

产物：
- `dist\v版本号-FileToolbox.exe`，例如 `dist\v1.1.2-FileToolbox.exe`

### macOS

```bash
bash ./scripts/build_macos.sh
```

产物：
- `dist/v版本号-FileToolbox.app`，例如 `dist/v1.1.2-FileToolbox.app`

### 图标

当前图标资源路径：
- `assets/icon.png`

构建时行为：
- Windows：会自动从 `icon.png` 生成 `icon.ico`
- macOS：若没有 `assets/icon.icns`，会尝试从 `icon.png` 生成

## GitHub Actions

当前已有工作流：
- [build-desktop.yml](C:/Users/vegta/Desktop/month_report_convert/.github/workflows/build-desktop.yml)

可通过以下方式自动构建：
- 手动运行 `Build Desktop Packages`
- 推送 `v*` tag

客户端版本号不需要手动维护。源码运行时会从本地 git tag 推断当前版本；打包时会自动生成 `gui_app/version.txt` 并打进客户端。正式发版只需要推送 tag，例如：

```powershell
git tag v1.1.2
git push origin v1.1.2
```

## 工程结构

### Word 转 PPT

- [docx_to_ppt_converter.py](C:/Users/vegta/Desktop/month_report_convert/docx_to_ppt_converter.py)：CLI 入口
- [report_converter/parsing.py](C:/Users/vegta/Desktop/month_report_convert/report_converter/parsing.py)：Word / OCR / 章节读取
- [report_converter/drafting.py](C:/Users/vegta/Desktop/month_report_convert/report_converter/drafting.py)：选材、改写、指标提取
- [report_converter/layout.py](C:/Users/vegta/Desktop/month_report_convert/report_converter/layout.py)：PPT 写回、续页、排版
- [report_converter/engine.py](C:/Users/vegta/Desktop/month_report_convert/report_converter/engine.py)：总控

### 脱敏 / 还原

- [sanitize_docx.py](C:/Users/vegta/Desktop/month_report_convert/sanitize_docx.py)：CLI 入口
- [doc_sanitizer/engine.py](C:/Users/vegta/Desktop/month_report_convert/doc_sanitizer/engine.py)：总控
- [doc_sanitizer/document_io.py](C:/Users/vegta/Desktop/month_report_convert/doc_sanitizer/document_io.py)：`docx/pptx` 读写、替换、还原
- [doc_sanitizer/scanning.py](C:/Users/vegta/Desktop/month_report_convert/doc_sanitizer/scanning.py)：候选识别与映射构建
- [doc_sanitizer/mapping.py](C:/Users/vegta/Desktop/month_report_convert/doc_sanitizer/mapping.py)：映射读写与编号
- [doc_sanitizer/patterns.py](C:/Users/vegta/Desktop/month_report_convert/doc_sanitizer/patterns.py)：规则与校验
- [doc_sanitizer/llm_assist.py](C:/Users/vegta/Desktop/month_report_convert/doc_sanitizer/llm_assist.py)：本地模型辅助识别

### GUI

- [gui_converter.py](C:/Users/vegta/Desktop/month_report_convert/gui_converter.py)：GUI 启动入口
- [gui_app/app.py](C:/Users/vegta/Desktop/month_report_convert/gui_app/app.py)：主程序与共享逻辑
- [gui_app/convert_tab.py](C:/Users/vegta/Desktop/month_report_convert/gui_app/convert_tab.py)：月报转 PPT 页签
- [gui_app/sanitize_tab.py](C:/Users/vegta/Desktop/month_report_convert/gui_app/sanitize_tab.py)：脱敏页签
- [gui_app/restore_tab.py](C:/Users/vegta/Desktop/month_report_convert/gui_app/restore_tab.py)：还原页签

## 当前已知限制

- OCR 数字提取仍可能需要人工复核
- 英文合同识别比中文月报更依赖人工审核
- 外部 AI 如果改坏了占位符，当前还原仍可能失败
- 后续建议加入“模糊占位符匹配 + 同一对象归并”能力
