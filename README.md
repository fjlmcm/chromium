# ungoogled-chromium 指纹伪装补丁

*基于ungoogled-chromium的浏览器指纹伪装增强版本*

## 项目概述

本项目是对ungoogled-chromium的增强版本，专注于提供更好的浏览器指纹伪装功能。在保持ungoogled-chromium原有隐私保护特性的基础上，增加了更完善的指纹伪装机制。

## 主要特性

### 核心改进

1. **系统字体保护**: 重构字体指纹伪装逻辑，确保系统默认字体始终可用，避免网页显示异常
2. **确定性随机化**: 使用基于种子的确定性算法替代真随机数，确保指纹的一致性
3. **平台适配**: 针对Windows、macOS、Linux提供不同的系统字体列表
4. **代码规范**: 严格遵循Chromium编码规范，移除所有中文注释

### 指纹伪装功能

- **字体指纹**: 智能屏蔽非系统字体，保护系统默认字体
- **用户代理**: 支持自定义操作系统、浏览器品牌和版本
- **硬件信息**: 可配置CPU核心数和内存大小
- **Canvas指纹**: 确定性的画布数据扰动
- **WebGL指纹**: GPU信息伪装
- **客户端矩形**: DOM元素尺寸微调

## 编译方式

本项目遵循ungoogled-chromium的标准编译流程：

```bash
# 1. 下载源码
mkdir -p build/download_cache
./utils/downloads.py retrieve -c build/download_cache -i downloads.ini
./utils/downloads.py unpack -c build/download_cache -i downloads.ini -- build/src

# 2. 清理二进制文件
./utils/prune_binaries.py build/src pruning.list

# 3. 应用补丁
./utils/patches.py apply build/src patches

# 4. 域名替换
./utils/domain_substitution.py apply -r domain_regex.list -f domain_substitution.list -c build/domsubcache.tar.gz build/src

# 5. 构建GN
mkdir -p build/src/out/Default
cd build/src
./tools/gn/bootstrap/bootstrap.py --skip-generate-buildfiles -j4 -o out/Default/

# 6. 编译
cp ../../flags.gn out/Default/args.gn
./out/Default/gn gen out/Default --fail-on-unused-args
ninja -C out/Default chrome chromedriver chrome_sandbox
```

## 使用方法

### 基本指纹伪装

```bash
# 使用指纹种子启动
chrome --fingerprint=12345

# 指定平台
chrome --fingerprint=12345 --fingerprint-platform=windows

# 自定义硬件信息
chrome --fingerprint=12345 --fingerprint-hardware-concurrency=8
```

### 高级配置

```bash
# 完整配置示例
chrome \
  --fingerprint=12345 \
  --fingerprint-platform=linux \
  --fingerprint-platform-version="Ubuntu 22.04" \
  --fingerprint-brand="Chrome" \
  --fingerprint-brand-version="120.0.6099.129" \
  --fingerprint-hardware-concurrency=16
```

## 技术改进

### 字体伪装优化

- **系统字体保护**: 确保Arial、Times New Roman等系统默认字体始终可用
- **平台特定**: 根据不同操作系统提供相应的系统字体列表
- **智能屏蔽**: 仅对非系统字体进行30%概率的屏蔽

### 确定性算法

- **FNV-1a哈希**: 使用标准哈希算法确保结果的确定性
- **种子混合**: 通过XOR操作混合指纹种子和输入数据
- **范围控制**: 精确控制随机化的范围和分布

### 代码质量

- **编码规范**: 严格遵循Chromium C++编码规范
- **注释规范**: 使用英文注释，符合开源项目标准
- **错误处理**: 增加参数验证和错误处理逻辑
- **内存安全**: 使用Chromium推荐的安全编程实践

## 版本信息

- **Chromium版本**: 134.0.6998.165
- **项目版本**: 2.0.0
- **最后更新**: 2024年12月

## 许可证

本项目继承ungoogled-chromium的BSD-3-Clause许可证。详见[LICENSE](LICENSE)文件。

## 贡献指南

1. 遵循Chromium编码规范
2. 确保所有补丁都能正确应用
3. 测试在不同平台上的兼容性
4. 提交前运行完整的编译测试

## 相关项目

- [ungoogled-chromium](https://github.com/ungoogled-software/ungoogled-chromium) - 上游项目
- [Bromite](https://github.com/bromite/bromite) - Android版本的隐私增强浏览器
- [Iridium Browser](https://iridiumbrowser.de/) - 另一个隐私导向的Chromium分支

## 支持

如有问题或建议，请通过GitHub Issues提交。
