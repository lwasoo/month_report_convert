# Word 月报转 PPT

把月报 `docx` 转成指定模板 `pptx`。  
默认通过本地 Ollama 模型（如 `qwen2.5:7b-instruct-q4_K_M`）生成每页要点；如果模型不可用，会自动回退到规则模式，确保可产出可编辑 PPT。

当前默认行为：
- 保留模板原有标题与版式（不改标题文本）
- 只在内容区写入匹配后的要点
- 运行全过程输出日志（读取、模型调用、写入页、导出）

## 1) 安装依赖

```powershell
python -m pip install python-docx python-pptx
```

## 2) 运行

```powershell
python .\docx_to_ppt_converter.py `
  --docx "C:\Users\vegta\Desktop\25立讯技术法务工作八月报_August_V1(2).docx" `
  --template "C:\Users\vegta\Desktop\法务部月汇报总结V1(1).pptx" `
  --output "C:\Users\vegta\Desktop\法务部月汇报总结_自动填充.pptx" `
  --model "qwen2.5:14b-instruct-q4_K_M" `
  --layout-mode formal `
  --theme formal_blue `
  --diversity none `
  --seed 7
```

## 3) 可选参数

- `--ollama-url`：默认 `http://127.0.0.1:11434`
- `--timeout`：单次模型调用超时秒数，默认 `180`
- `--retries`：模型失败重试次数，默认 `2`
- `--no-llm`：关闭模型，只用规则匹配与改写
- `--layout-mode`：内容排版模式（`classic`/`formal`，默认 `classic`）
- `--theme`：正式布局主题（`formal_blue`/`corporate_gray`/`legal_red`）
- `--diversity`：版式多样化程度（`none`/`low`/`medium`/`high`，其中 `none` 为不套用多样化布局）
- `--seed`：版式随机种子（同 seed 可复现）

## 4) 实现原理

### 4.1 总体流程

1. 读取 Word，抽取段落并按“标题候选规则”切分章节。  
2. 读取 PPT 模板，识别需要填充的页面（默认第 2-11 页）。  
3. 按“页面标题关键词”从 Word 中选素材句。  
4. 调用 LLM 做“PPT 风格改写”（保留 BU/项目/案件/日期/数字）。  
5. 结果再做规则校验（页内主题匹配、去重、低质量句替换）。  
6. 回写到模板内容区并导出 `.pptx`。

### 4.2 为什么这样设计

- **LLM 做改写，程序做约束**：模型负责“怎么说”，代码负责“放在哪页、能不能放、是否重复”。  
- **模板优先**：不改标题、不改版式，避免输出偏离汇报模板。  
- **可留空**：某页素材证据不足时允许空白，不强行填错内容。  
- **可回退**：模型失败时自动走规则模式，保证链路可用。

### 4.3 页面匹配策略

- 每页先根据标题建立关键词集合（例如“知识产权页”优先专利/IP相关词）。  
- 再按评分从素材池排序抽取。  
- 对关键页应用强约束：
  - “美国劳动诉讼”页需同时命中“美国”与“劳动/诉讼/仲裁”等词。
  - “337”页只收 `337/TA1484` 相关句。
- 对专项页应用白名单/黑名单（如知识产权页过滤仲裁诉讼句）。

### 4.4 去重与清洗

- 去重分两层：
  - 页内去重（同页不重复）
  - 跨页去重（后页尽量不复用前页语句）
- 清洗内容包括：
  - 去编号前缀（如 `1.`、`（1）`）
  - 修正常见脏词
  - 去掉空白噪声与多余分隔符

### 4.5 数据页处理

- 第 5 页保留表格并填第二列。  
- 若 Word 有明确数字（如 638 / 601 / 专利提案 16 / 调查 53）则写入；  
  未出现的指标填 `-`。

## 5) 当前已知限制

- 7B 模型对长指令/长上下文稳定性有限，偶尔会输出宽泛句。  
- 若模板标题与实际文档主题偏差大，仍可能需要人工调整页面归属。  
- 强约束页（如“美国劳动诉讼”）在证据不足时会空白，这是预期行为。

## 6) 工程结构（模块化）

- `docx_to_ppt_converter.py`：Word 转 PPT CLI 入口
- `sanitize_docx.py`：文档脱敏 / 还原 CLI 入口
- `gui_converter.py`：GUI 启动入口（仅做转发）

### 6.1 Word 转 PPT 路径

- `report_converter/parsing.py`：Word / OCR / 章节读取
- `report_converter/drafting.py`：选材、改写、指标提取
- `report_converter/layout.py`：PPT 写回、分页、排版
- `report_converter/engine.py`：总控编排

### 6.2 脱敏 / 还原路径

- `doc_sanitizer/engine.py`：脱敏扫描、映射合并、写回、还原
- `report_converter/sanitizer.py`：兼容导出层（转发到 `doc_sanitizer`）

### 6.3 GUI 路径

- `gui_app/app.py`：GUI 主程序与共享逻辑
- `gui_app/convert_tab.py`：月报转 PPT 页签逻辑
- `gui_app/sanitize_tab.py`：脱敏页签逻辑
- `gui_app/restore_tab.py`：还原页签逻辑

## 7) GUI 使用

```powershell
python .\gui_converter.py
```

- 启动后会自动检测本机 Ollama 模型并填充下拉列表。
- 也可点击“检测模型”手动刷新模型列表。
- 可在“排版模式”选择 `formal`（正式汇报布局）或 `classic`（旧版布局）。
- `formal` 下可继续选择主题、版式多样化程度与 `seed`。
- 选择 `Word 路径`、`模板路径`、`输出路径` 后点击“开始转换”。
- 下方“运行日志”会实时显示转换过程和错误信息。

## 8) 打包成客户端（Windows/macOS）

### 8.1 Windows 一键打包 EXE

```powershell
cd C:\Users\vegta\Desktop\month_report_convert
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

产物：
- `dist\MonthReportConverter.exe`

### 8.2 macOS 打包 .app

```bash
cd /path/to/month_report_convert
bash ./scripts/build_macos.sh
```

产物：
- `dist/MonthReportConverter.app`

### 8.3 GitHub 自动构建（跨电脑推荐）

仓库已提供工作流：
- `.github/workflows/build-desktop.yml`

触发方式：
- 打 tag（如 `v1.0.0`）后自动构建 Windows + macOS 产物
- 或在 GitHub Actions 手动点 `Build Desktop Packages`

### 8.4 对方电脑首次使用前置条件

客户端本身可即开即用，但推理依赖本机 Ollama：

1. 安装并启动 Ollama  
2. 拉取模型（例如）：

```bash
ollama pull qwen2.5:14b-instruct-q4_K_M
```

3. 确保 `http://127.0.0.1:11434` 可访问

> 如果未满足前置条件，GUI 会在“检测模型/运行日志”里提示失败原因。
## 9) Word 脱敏 / 还原

当前已支持 `docx` 文件的本地脱敏与还原，适合把合同、月报、法务材料先做占位符替换，再交给外部 AI 处理。

输出包含两部分：
- 脱敏后的 `docx`
- 映射文件 `json`

占位符示例：
- `__COMPANY_001__`
- `__AMOUNT_001__`
- `__TITLE_001__`
- `__PROJECT_001__`

### 9.1 CLI 脱敏

```powershell
python .\sanitize_docx.py sanitize `
  --input "C:\input.docx" `
  --output "C:\input_脱敏.docx" `
  --mapping "C:\input_映射.json"
```

### 9.2 CLI 还原

```powershell
python .\sanitize_docx.py restore `
  --input "C:\input_脱敏_AI修改后.docx" `
  --output "C:\input_还原.docx" `
  --mapping "C:\input_映射.json"
```

### 9.3 自定义敏感词

可额外传入一份词表文件（一行一个）：

```powershell
python .\sanitize_docx.py sanitize `
  --input "C:\input.docx" `
  --output "C:\input_脱敏.docx" `
  --mapping "C:\input_映射.json" `
  --terms-file "C:\terms.txt"
```

### 9.3.1 可选 AI 辅助识别

脱敏现在默认会优先使用本机 Ollama 做辅助识别；如果要关闭，可显式传 `--no-llm-assist`。

如果本机已启动 Ollama，可直接这样使用：

```powershell
python .\sanitize_docx.py sanitize `
  --input "C:\input.docx" `
  --output "C:\input_脱敏.docx" `
  --mapping "C:\input_映射.json" `
  --use-llm-assist `
  --model "qwen2.5:7b-instruct-q4_K_M" `
  --ollama-url "http://127.0.0.1:11434"
```

说明：
- AI 辅助只用于“补充候选敏感项”，不会参与还原
- 程序会把文档按段分块送给本地模型识别
- 最终仍建议在 GUI 的 `映射审核` 区人工确认
- 如果模型不可用或调用失败，程序会自动回退到规则识别

### 9.4 当前默认识别的敏感项

- 公司主体
- 诉讼 / 仲裁中的部分人名（按上下文与姓名模式识别）
- 甲方 / 乙方 / 丙方
- 金额
- 合同或材料标题（`《...》`）
- 项目名称
- 案号 / 合同编号
- 客户 / 供应商字段
- 邮箱 / 手机号 / 长数字账号
- 部分代码类标识（如项目编码、案件编码）

### 9.5 GUI 审核流

GUI 现在拆成两个独立页签：`脱敏` 和 `还原`。

`脱敏` 页签走两阶段流程：

1. 先点 `识别候选映射`
2. 程序只生成内存中的候选映射，不会先输出脱敏文档和 JSON
3. 在下方 `映射审核` 区修改
4. 你可以：
   - 启用 / 禁用某条替换
   - 删除误识别项
   - 手动新增映射：`敏感词` + `替换为`
   - 勾选“启用本地模型辅助识别”后再重跑脱敏
5. 确认没问题后，再点 `生成脱敏文档`
6. 这一步才会真正输出：
   - 脱敏后的 `docx`
   - 最终映射 `json`

这样可以保留前面已经确认过的映射，再继续补新映射，不需要每次从头来。

### 9.6 当前策略说明

- 自动识别目前是**偏保守**的：宁可少替一点，再交给人工补。
- 映射文件现在使用 `entries` 结构，包含：
  - `original`
  - `placeholder`
  - `category`
  - `enabled`
  - `source`
- `restore` 时会按映射文件把占位符还原回原文。

GUI 里也已新增单独的 `脱敏 / 还原` 页签。
