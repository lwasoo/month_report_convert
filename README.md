# Word 月报转 PPT（模板填充）

把法务月报 `docx` 转成指定模板 `pptx`。  
默认通过本地 Ollama 模型（如 `qwen2.5:7b-instruct-q4_K_M`）生成每页要点；如果模型未就绪，会自动走规则兜底，保证能产出可编辑 PPT。

当前版本默认行为：
- 保留模板原有标题与版式（不改标题文本）
- 只在内容区写入匹配要点
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
  --model "qwen2.5:7b-instruct-q4_K_M"
```

## 3) 可选参数

- `--ollama-url`：默认 `http://127.0.0.1:11434`
- `--timeout`：单次模型调用超时秒数，默认 `180`
- `--retries`：模型失败重试次数，默认 `2`
- `--no-llm`：关闭模型，只用规则匹配

## 4) 当前实现说明

- 第 2-11 页按模板标题匹配 Word 内容并填入要点。
- 默认不改模板标题与封面文案。
- 第 5 页会填两张表格的第二列（缺失数据用 `-`）。
- 输出是标准可编辑 `.pptx`。

## 5) 工程结构（已模块化）

- `docx_to_ppt_converter.py`：CLI 入口（参数解析 + 调用）
- `report_converter/constants.py`：指标标签常量
- `report_converter/models.py`：数据结构（SlideDraft / TemplateSlide）
- `report_converter/engine.py`：核心逻辑（解析、匹配、LLM改写、写回PPT）
