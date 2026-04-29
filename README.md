# 月报工具箱

把法务月报 `Word(.docx)` 转成模板 `PPT(.pptx)`，并支持 `Word / PPT` 的脱敏与还原。

当前包含 3 个主要功能：
- `月报转 PPT`：把月报 Word 填进固定 PPT 模板
- `文档脱敏`：把敏感词替换成占位符，适合交给外部 AI 继续处理
- `文档还原`：把占位符恢复成原始敏感词

## 1. 适合谁用

适合下面这种流程：

1. 原始 Word 月报先脱敏
2. 把脱敏后的 Word 交给外部 AI，或继续转成 PPT
3. 最后对生成的 Word / PPT 再做敏感词还原

## 2. Prerequisites

使用前建议先准备好这些环境。

### 2.1 必需

- Windows 或 macOS
- Python `3.10+`
- 本项目代码

### 2.2 如果要用本地模型

需要安装并启动 `Ollama`。

下载：
- [Ollama 官网](https://ollama.com/download)

安装后确认服务可用：

```powershell
ollama list
```

如果你的模型目录不在默认位置，还需要设置：

```powershell
[Environment]::SetEnvironmentVariable('OLLAMA_MODELS', 'D:\Ollama\your\model\path', 'User')
```

然后重启 Ollama。

### 2.3 推荐模型

至少准备一个：

```powershell
ollama pull qwen2.5:7b-instruct-q4_K_M
```

如果机器配置更高，也可以用：

```powershell
ollama pull qwen2.5:14b-instruct-q4_K_M
```

> 不建议使用参数过小的的模型，会影响识别效果。

## 3. 源码安装

进入项目目录后安装运行依赖：

```powershell
python -m pip install -r .\requirements.txt
```

如果你还要本地打包 exe / app，再安装打包依赖：

```powershell
python -m pip install -r .\requirements-build.txt
```

`requirements.txt` 当前主要包括：
- `python-docx`
- `python-pptx`
- `Pillow`
- `numpy`
- `rapidocr-onnxruntime`

## 4. 最简单的打开方式

直接启动 GUI：

```powershell
python .\gui_converter.py
```

GUI 目前有 3 个页签：
- `月报转 PPT`
- `脱敏`
- `还原`

## 5. 月报转 PPT

### 5.1 GUI 用法

在 `月报转 PPT` 页签里填：
- 原始 `docx`
- 模板 `pptx`
- 输出 `pptx`
- 模型名

然后点开始转换。

### 5.2 CLI 用法

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

### 5.3 常用参数

- `--ollama-url`：默认 `http://127.0.0.1:11434`
- `--timeout`：默认 `180`
- `--retries`：默认 `2`
- `--no-llm`：关闭模型，只用规则模式
- `--layout-mode`：`classic` / `formal`
- `--theme`：`formal_blue` / `corporate_gray` / `legal_red`
- `--diversity`：`none` / `low` / `medium` / `high`
- `--seed`：固定版式随机种子

### 5.4 当前行为

- 保留模板标题，不改标题文本
- 只往内容区写入要点
- 放不下时自动续页
- 有表格时会尽量避让表格区域
- 模型失败时回退规则模式

## 6. 文档脱敏

当前支持：
- `docx`
- `pptx`

输出包含两部分：
- 脱敏后的文件
- 映射文件 `json`

占位符示例：
- `__COMPANY_001__`
- `__PERSON_003__`
- `__PROJECT_002__`

### 6.1 GUI 脱敏流程

推荐流程：

1. 选原始文件
2. 点 `识别候选映射`
3. 在下方表格人工审核
4. 再点 `生成脱敏文档`

表格里可以：
- 搜索某个词是否被识别
- 双击直接编辑 `类别 / 敏感词 / 替换为`
- 启用或禁用选中项
- 删除误识别项
- 手工新增单条映射
- 批量添加映射
- 载入旧的映射 `JSON` 继续审核

### 6.2 CLI 脱敏

```powershell
python .\sanitize_docx.py sanitize `
  --input "C:\input.docx" `
  --output "C:\input_脱敏.docx" `
  --mapping "C:\input_映射.json"
```

脱敏 `pptx` 也是一样：

```powershell
python .\sanitize_docx.py sanitize `
  --input "C:\input.pptx" `
  --output "C:\input_脱敏.pptx" `
  --mapping "C:\input_映射.json"
```

### 6.3 AI 辅助识别

脱敏默认优先用本地 Ollama 辅助识别。

```powershell
python .\sanitize_docx.py sanitize `
  --input "C:\input.docx" `
  --output "C:\input_脱敏.docx" `
  --mapping "C:\input_映射.json" `
  --use-llm-assist `
  --model "qwen2.5:7b-instruct-q4_K_M"
```

如果要关闭模型，只用规则：

```powershell
python .\sanitize_docx.py sanitize `
  --input "C:\input.docx" `
  --output "C:\input_脱敏.docx" `
  --mapping "C:\input_映射.json" `
  --no-llm-assist
```

### 6.4 外部 AI 使用注意

把脱敏文件交给外部 AI 时：

- 可以删减内容
- 可以改写句子
- 不要修改、拆分、翻译或删除占位符

例如这些必须原样保留：
- `__COMPANY_001__`
- `__PERSON_003__`

否则后续无法正确还原。

## 7. 文档还原

当前支持：
- `docx`
- `pptx`

### 7.1 GUI 用法

在 `还原` 页签里填：
- AI 修改后的文件
- 映射 `json`
- 输出文件路径

然后点开始还原。

### 7.2 CLI 用法

```powershell
python .\sanitize_docx.py restore `
  --input "C:\input_脱敏_AI修改后.docx" `
  --output "C:\input_还原.docx" `
  --mapping "C:\input_映射.json"
```

还原 `pptx`：

```powershell
python .\sanitize_docx.py restore `
  --input "C:\input_脱敏_AI修改后.pptx" `
  --output "C:\input_还原.pptx" `
  --mapping "C:\input_映射.json"
```

## 8. 推荐实战流程

### 8.1 月报直接转 PPT

1. 原始月报 `docx`
2. 直接转成模板 `pptx`
3. 人工审核 PPT

### 8.2 敏感月报外发处理

1. 原始月报 `docx` 先脱敏
2. 脱敏后的 `docx` 去转 `ppt`
3. 对生成的 `ppt` 再做还原

这条链路当前已经实测跑通。

**需要注意：**
- 只有最终 `PPT` 里还保留的占位符，才会被还原
- 如果外部 AI 把某段内容整段删掉，对应敏感词不会凭空恢复

## 9. 打包

### 9.1 Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

产物：
- `dist\MonthReportConverter.exe`

### 9.2 macOS

```bash
bash ./scripts/build_macos.sh
```

产物：
- `dist/MonthReportConverter.app`

### 9.3 GitHub Actions

仓库里已经有：
- [`.github/workflows/build-desktop.yml`](C:/Users/vegta/Desktop/month_report_convert/.github/workflows/build-desktop.yml)

可以通过：
- 手动运行 `Build Desktop Packages`
- 或推送 `v*` tag

来自动构建桌面产物。

## 10. 工程结构

### 10.1 Word 转 PPT

- [`docx_to_ppt_converter.py`](C:/Users/vegta/Desktop/month_report_convert/docx_to_ppt_converter.py)：CLI 入口
- [`report_converter/parsing.py`](C:/Users/vegta/Desktop/month_report_convert/report_converter/parsing.py)：Word / OCR / 章节读取
- [`report_converter/drafting.py`](C:/Users/vegta/Desktop/month_report_convert/report_converter/drafting.py)：选材、改写、指标提取
- [`report_converter/layout.py`](C:/Users/vegta/Desktop/month_report_convert/report_converter/layout.py)：PPT 写回、续页、排版
- [`report_converter/engine.py`](C:/Users/vegta/Desktop/month_report_convert/report_converter/engine.py)：总控

### 10.2 脱敏 / 还原

- [`sanitize_docx.py`](C:/Users/vegta/Desktop/month_report_convert/sanitize_docx.py)：CLI 入口
- [`doc_sanitizer/engine.py`](C:/Users/vegta/Desktop/month_report_convert/doc_sanitizer/engine.py)：总控入口
- [`doc_sanitizer/document_io.py`](C:/Users/vegta/Desktop/month_report_convert/doc_sanitizer/document_io.py)：`docx/pptx` 读取、替换、还原
- [`doc_sanitizer/scanning.py`](C:/Users/vegta/Desktop/month_report_convert/doc_sanitizer/scanning.py)：候选识别与映射构建
- [`doc_sanitizer/mapping.py`](C:/Users/vegta/Desktop/month_report_convert/doc_sanitizer/mapping.py)：映射读写与编号
- [`doc_sanitizer/patterns.py`](C:/Users/vegta/Desktop/month_report_convert/doc_sanitizer/patterns.py)：规则与校验
- [`doc_sanitizer/llm_assist.py`](C:/Users/vegta/Desktop/month_report_convert/doc_sanitizer/llm_assist.py)：本地模型辅助识别

### 10.3 GUI

- [`gui_converter.py`](C:/Users/vegta/Desktop/month_report_convert/gui_converter.py)：GUI 启动入口
- [`gui_app/app.py`](C:/Users/vegta/Desktop/month_report_convert/gui_app/app.py)：主程序与共享逻辑
- [`gui_app/convert_tab.py`](C:/Users/vegta/Desktop/month_report_convert/gui_app/convert_tab.py)：月报转 PPT 页签
- [`gui_app/sanitize_tab.py`](C:/Users/vegta/Desktop/month_report_convert/gui_app/sanitize_tab.py)：脱敏页签
- [`gui_app/restore_tab.py`](C:/Users/vegta/Desktop/month_report_convert/gui_app/restore_tab.py)：还原页签

## 11. 当前已知限制

- OCR 数字提取还不是完全稳定，图片表格可能仍需人工核对
- 英文合同识别比中文月报更依赖人工审核
- 脱敏类别目前仍可能出现漂移，审核阶段建议手工校正
- 如果外部 AI 改坏了占位符，系统无法自动还原
