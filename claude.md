# Fingerprint Chromium 项目编码规范

## 项目概述
本项目是基于 Ungoogled Chromium 的 Windows 版本补丁，添加了浏览器指纹伪装功能。项目需要严格遵循 Windows 构建环境兼容性要求。

## 文件编码规范

### 1. 字符编码
- 所有文件使用 UTF-8 编码（无BOM）
- 补丁文件（.patch）必须使用 UTF-8 编码
- 避免使用中文注释，所有注释使用英文

### 2. 行尾符格式
- 所有文件使用 LF（Unix格式）作为行尾符
- 禁止使用 CRLF（Windows格式）行尾符
- 确保在 Windows 下编译不出现格式错误

### 3. 文件结构
- 补丁文件存放在 `patches/` 目录下
- 核心补丁在 `patches/core/` 
- 扩展补丁在 `patches/extra/`
- 指纹伪装补丁在 `patches/extra/fingerprint/`

## 代码格式规范

### 1. C++ 代码风格
- 遵循 Chromium 项目编码风格
- 使用 2 个空格进行缩进，不使用制表符
- 头文件包含顺序遵循 Chromium 标准
- 命名空间使用标准 Chromium 约定

### 2. 补丁文件格式
- 补丁文件必须遵循标准 diff 格式
- 路径格式：使用正斜杠 `/` 而非反斜杠 `\`
- 删除行使用 `-` 前缀，添加行使用 `+` 前缀
- 上下文行保持原样，不修改缩进

### 3. 构建文件
- `flags.gn` 文件使用标准 GN 语法
- 布尔值使用 `true`/`false`，不使用 `1`/`0`
- 字符串值使用双引号包围

## Windows 兼容性规范

### 1. 条件编译
```cpp
#if BUILDFLAG(IS_WIN)
// Windows specific code
#endif  // BUILDFLAG(IS_WIN)
```

### 2. 路径处理
- 使用标准 Chromium 路径 API
- 避免硬编码平台特定路径
- 保持原有路径引用不变

### 3. Windows 特定功能
- 禁用下载隔离功能（Zone Identifier）
- 移除 Windows 安全检查相关代码
- 确保 Windows API 调用的兼容性

## 指纹伪装功能规范

### 1. 命令行参数
指纹控制通过以下命令行参数实现：
- `--fingerprint`: 基础指纹种子
- `--fingerprint-brand`: 浏览器品牌
- `--fingerprint-brand-version`: 浏览器版本
- `--fingerprint-gpu-vendor`: GPU 厂商
- `--fingerprint-gpu-renderer`: GPU 渲染器
- `--fingerprint-hardware-concurrency`: CPU 核心数
- `--fingerprint-platform`: 操作系统平台
- `--fingerprint-platform-version`: 操作系统版本

### 2. 实现模式
- 使用 `base::CommandLine::ForCurrentProcess()` 获取参数
- 在相应的 WebAPI 实现中添加参数检查
- 优先返回自定义值，否则返回系统默认值

### 3. 修改的 API
- Navigator.userAgent
- Navigator.platform  
- Navigator.hardwareConcurrency
- Navigator.deviceMemory (固定为8GB)
- WebGL 渲染器信息
- Canvas 指纹
- 客户端提示（Client Hints）

## 构建配置规范

### 1. flags.gn 配置
```gn
# 禁用 Google 服务
google_api_key=""
google_default_client_id=""
google_default_client_secret=""
use_official_google_api_keys=false

# 禁用可选功能
enable_nacl=false
enable_remoting=false
enable_reporting=false
safe_browsing_mode=0
```

### 2. 组件移除
- 移除 Screen AI 相关组件
- 禁用隐私沙盒功能
- 移除 Google 服务依赖
- 禁用自动更新功能

## 代码审查规范

### 1. 修改检查清单
- [ ] 无中文注释
- [ ] 使用 LF 行尾符
- [ ] 遵循 Chromium 编码风格  
- [ ] Windows 兼容性测试通过
- [ ] 不改变原有路径引用
- [ ] 补丁格式正确

### 2. 测试要求
- 在 Windows 环境下编译成功
- 指纹伪装功能正常工作
- 不破坏原有 Chromium 功能
- 与 Ungoogled Chromium 补丁兼容

## 注意事项

### 1. 禁止行为
- 添加中文注释
- 使用 Windows 格式行尾符
- 修改原有文件路径
- 引入不必要的依赖

### 2. 维护建议
- 定期同步上游 Ungoogled Chromium 更新
- 保持补丁文件最小化
- 记录每个修改的目的和理由
- 测试不同 Windows 版本的兼容性

### 3. 构建环境
- 使用官方 Chromium 构建工具链
- 确保 Windows SDK 版本兼容性
- 验证所有必需的构建依赖
- 测试增量构建和完整构建

## Git 工作流程
- 每次修改完成后提交到 GitHub 仓库的 136.0.7103.113 标签
- 使用强制更新 (--force) 覆盖标签
- 始终保持 master 分支与标签同步

### 推送流程
- GitHub仓库: https://github.com/fjlmcm/chromium
1. `git add .` - 添加所有更改
2. `git commit -m "..."` - 提交更改
3. `git push origin master --force` - 强制推送主分支
4. `git tag -f 136.0.7103.113` - 更新标签
5. `git push origin 136.0.7103.113 --force` - 强制推送标签


## 字体伪装优化更新

### 新增补丁文件
1. **020-font-virtualization.patch** - 字体虚拟化支持
   - 实现高级字体映射机制
   - 支持专业字体、创意字体、Web字体的虚拟化
   - 基于指纹哈希动态选择可用字体列表

2. **021-font-enumeration-api.patch** - 字体枚举API保护
   - 保护Font Access API查询结果
   - 提供一致但多样化的字体列表
   - 支持CJK字体的指纹保护

### 字体伪装特性
- **分类字体管理**: 按功能将字体分组（系统字体、Office字体、Web字体等）
- **智能概率过滤**: 根据字体特征调整可用性概率
- **跨平台兼容**: 支持Windows、macOS、Linux字体的统一处理
- **国际化支持**: 包含中日韩字体的完整保护

### 测试工具
- **test_font_fingerprint.html**: 完整的字体指纹测试套件
  - 字体可用性检测
  - Canvas字体渲染测试
  - CSS字体检测
  - Font Access API测试

### 使用说明
```bash
# 启用字体伪装的示例命令
./chrome --fingerprint=123456789 --fingerprint-platform=windows
```

### 技术改进
1. **增强的字体过滤算法**
   - 从简单的5%概率提升到15%基础概率
   - 根据字体类型动态调整概率（Symbol字体2%，长名称8%等）
   - 特殊字体（Wingdings等）极低概率显示

2. **字体虚拟化映射**
   - 高端字体映射到常见字体（Adobe Garamond Pro → Times New Roman）
   - 保持渲染一致性的同时提供指纹保护
   - 支持基于哈希范围的确定性映射

3. **系统集成优化**
   - 集成到FontCache核心逻辑
   - 支持CSS解析器的字体虚拟化
   - 保护浏览器字体枚举API

## 版本信息
- 基于版本: Ungoogled Chromium 136.0.7103.113-1.1
- 目标平台: Windows x64
- 编译工具链: Visual Studio 2019/2022
- 更新日期: 2025年9月
- 字体伪装优化: v2.0