# 回归测试

测试目录与运行代码的职责对应，共享的脚本化模型客户端和合成控制集中在support/。文件名保留具体科学边界，便于定位失败的假设或数值约定。

| 目录 | 范围 |
| --- | --- |
| evaluation/ | workflow表达式、能力依赖、科学结果、参考身份与评分边界 |
| tools/ | 科学原语、协议适配、数值与对象身份；外部服务使用明确的离线夹具 |
| baselines/ | ReAct、SciToolAgent、模型接入、上下文、格式、循环与批处理 |
| runtime/ | 工具契约、worker、参数验证、超时与附件隔离 |
| integration/ | 项目CLI、资源安装、数据读取和跨组件接口 |

在SciTool-Unified环境安装测试依赖后运行：

```bash
python -m pip install -e ".[test]"
python -m pytest tests -q
python -m pytest tests/evaluation -q
python -m pytest tests/tools/test_chemical_consolidation.py -q
```

正式500题的参考完整性和自评分由`python cli.py validate`验证。静态资源预检使用`python -m scripts.tools.check_foundation`。离线测试通过不表示所有远程服务现场可用；需要账号、权重或现场计算的验收应另记实际调用结果。
