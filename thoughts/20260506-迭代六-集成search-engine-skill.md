# 思考过程 - 20260506 迭代六

## 本次更新内容

1. **新增SkillSearchProvider** - 集成../search-engine中的skill进行搜索
2. **更新config.py** - 添加搜索方式配置，支持"skill"和"tavily"两种模式
3. **更新searcher.py** - 重构StockSearcher初始化，支持通过配置选择搜索提供者
4. **更新researcher.py** - 使用新的搜索配置初始化搜索器
5. **更新.env.example** - 添加搜索相关配置项

## 实现细节

### SkillSearchProvider设计

SkillSearchProvider类主要功能：
- 动态导入../search-engine中的skill模块
- 调用skill.search()函数进行搜索
- 支持普通搜索和定向搜索(targeted)
- 支持mock模式
- 格式化skill返回的结果为统一格式
- 集成ContentCleaner进行内容过滤

### 搜索提供者选择

StockSearcher初始化支持两种方式：
1. 直接传入search_provider实例（兼容旧代码）
2. 通过search_provider_type参数选择"skill"或"tavily"

### 配置项说明

.env中新增的配置：
- SEARCH_PROVIDER: 选择"skill"（默认）或"tavily"
- SEARCH_ENGINE_PATH: search-engine目录路径（默认"../search-engine"）
- SKILL_USE_TARGETED: 是否使用skill的定向搜索（仅优质站点）
- SKILL_USE_MOCK: 是否使用skill的mock模式

### 搜索流程

当使用skill搜索时：
1. 先使用完整query搜索
2. 如果结果不足，尝试用简化后的关键词搜索
3. 合并结果并去重
4. 通过ContentCleaner过滤无效内容
5. 返回结果

## 需要注意的点

1. **路径导入** - 需要确保search-engine目录在Python路径中
2. **异常处理** - 如果skill导入失败或搜索失败，不应该中断程序
3. **兼容性** - 保持对旧代码的兼容，TavilySearchProvider仍然可用
4. **配置验证** - 当选择skill模式时，需要检查search-engine目录是否存在

## 后续优化方向

1. **搜索结果回写** - 可以将skill搜索的结果回写到search-engine的search_results目录
2. **参数传递** - 支持更多skill参数配置（如time_range, num_results等）
3. **历史查询** - 集成skill的query_history功能，避免重复搜索
