# 答辩论证数据与规模场景

> owner: AI-OUTLINE ｜ version: 3.0 ｜ status: 已计算并用于8页审阅稿 ｜ updated: 2026-10-28

[事实与场景JSON](evidence-and-scenarios.json)用于本轮PPT第2、3、7、8页。全国教育、文献、调查、湖北教育和采购案例分别保留来源与口径；规划场景独立登记，不混入事实指标。关联入口为已登记的[AI答辩大纲视觉清单](../AI答辩大纲视觉清单.md)。

| 数据 | 来源与范围 | 本轮用法 |
| --- | --- | --- |
| 2025教育规模 | [教育部统计公报](https://www.moe.gov.cn/jyb_sjzl/sjzl_fztjgb/202607/t20260706_1442870.html)，2026-07-06发布 | 3,167所高等学校含成人高校；3,953.96万学生限普通、职业本专科；不求校均值或客户人数 |
| 本科抑郁症状检出率 | [Zhou等2024，Table 1](https://capmh.biomedcentral.com/counter/pdf/10.1186/s13034-024-00841-w.pdf)，CC BY 4.0 | 本科研究亚组188项、报告样本374,996、27.72%及95%CI；I²=100%；不能当作当前全国临床患病率 |
| 咨询服务知晓与使用 | [出版商摘要](https://cpms.ssap.com.cn/skwx_cmr/initDatabaseDetail?contentId=8225479&contentType=literature&siteId=23)确认2024年本科有效问卷60,782份；[作者公开摘要](https://psy.china.com.cn/2025-06/20/content_43141390.htm)及[同文繁体入口](https://big5.china.com.cn/gate/big5/psy.china.com.cn/2025-06/20/content_43141390.htm)报告80.0%/2.8% | 独立问题比例，不做漏斗或因果解释；按数据重建原生图，不复制原网页图片 |
| 2026政策 | [教体艺〔2026〕3号](https://www.moe.gov.cn/srcsite/A17/moe_943/moe_946/202602/t20260227_1429365.html) | 规范监测和科学应用的政策要求，不报告为各校已完成 |
| 湖北2024教育 | [项目教育数据登记](../../plan/ai-application/revision-20261027/regional-education-2024.json)中的教育部三表 | 普通/职业高校133、本专科1,915,173人；仅作切入区域背景 |
| 高校采购实践 | [中国劳动关系学院2026-09-09成交公告](https://www.ccgp.gov.cn/cggg/zygg/cjgg/202609/t20260909_27295534.htm) | 45万元为含测评、陪伴、培训、平台和部署的复合包；不是心域智链单价或订单 |

每校5,000人、每人每学期2条记录、20%记录按任务规则生成摘要，均是本轮规划参数。1/5/10校对应5,000/25,000/50,000人，每学期10,000/50,000/100,000条记录及2,000/10,000/20,000份摘要。20%不是心理风险率；这些算术场景不表示容量实测或承诺。计算脚本、构建和核对证据保留于项目私有`tmp/ai-outline-20261028/defense-rationale-v3/`。

图像沿用已登记的[AI概念插画](../defense-ai-assets-20261028/manifest.json)及[Phosphor图标](../material-library-design-20261028/content-pack/README.md)，未将旧资产计为本轮新生成。第6页沿用[完全合成数据](../defense-ai-assets-20261028/data-demo.json)；统计事实由代码计算，目标摘要为人工拟写，未调用真实业务模型或读取学生数据。
