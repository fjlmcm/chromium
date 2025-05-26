# 部署指南

## 概述

本指南说明如何将重构后的 Ungoogled Chromium 指纹防护补丁部署到目标仓库。

## 目标仓库信息

- **仓库地址**: https://github.com/fjlmcm/chromium
- **目标标签**: 134.0.6998.165
- **部署方式**: 强制更新

## 部署步骤

### 1. 准备工作

```bash
# 克隆目标仓库
git clone https://github.com/fjlmcm/chromium.git
cd chromium

# 切换到目标标签
git checkout 134.0.6998.165

# 创建新的工作分支
git checkout -b refactored-fingerprint-patches
```

### 2. 复制重构后的文件

将以下重构后的文件复制到对应位置：

```bash
# 复制补丁文件
cp -r patches/ /path/to/chromium/patches/

# 复制配置文件
cp chromium_version.txt /path/to/chromium/
cp revision.txt /path/to/chromium/
cp flags.gn /path/to/chromium/
cp domain_regex.list /path/to/chromium/
cp domain_substitution.list /path/to/chromium/
cp pruning.list /path/to/chromium/
cp downloads.ini /path/to/chromium/

# 复制工具脚本
cp -r utils/ /path/to/chromium/utils/
cp -r devutils/ /path/to/chromium/devutils/
```

### 3. 验证文件完整性

```bash
# 检查关键文件是否存在
ls -la patches/extra/fingerprint/
ls -la patches/series
ls -la chromium_version.txt
```

### 4. 提交更改

```bash
# 添加所有更改
git add .

# 提交更改
git commit -m "重构指纹防护补丁

- 移除中文注释，使用英文注释
- 优化字体伪装功能，避免屏蔽系统默认字体
- 改进代码风格，遵循Chromium编码规范
- 最小化修改，保持功能完整性
- 更新GPU信息数据库
- 规范化所有指纹防护补丁

版本: 134.0.6998.165
兼容性: 完全兼容ungoogled-chromium构建流程"
```

### 5. 强制推送到目标标签

```bash
# 强制推送到134.0.6998.165标签
git tag -f 134.0.6998.165
git push origin 134.0.6998.165 --force

# 推送分支（可选）
git push origin refactored-fingerprint-patches
```

## 构建验证

### 1. 基本构建测试

```bash
# 下载源码
mkdir -p build/download_cache
./utils/downloads.py retrieve -c build/download_cache -i downloads.ini
./utils/downloads.py unpack -c build/download_cache -i downloads.ini -- build/src

# 修剪二进制文件
./utils/prune_binaries.py build/src pruning.list

# 应用补丁
./utils/patches.py apply build/src patches

# 域名替换
./utils/domain_substitution.py apply -r domain_regex.list -f domain_substitution.list -c build/domsubcache.tar.gz build/src

# 构建GN
mkdir -p build/src/out/Default
cd build/src
./tools/gn/bootstrap/bootstrap.py --skip-generate-buildfiles -j4 -o out/Default/

# 配置构建
cp ../../flags.gn out/Default/args.gn
./out/Default/gn gen out/Default --fail-on-unused-args

# 开始构建（测试）
ninja -C out/Default chrome chromedriver chrome_sandbox
```

### 2. 功能验证

构建完成后，验证指纹防护功能：

```bash
# 启动浏览器进行测试
./out/Default/chrome \
  --fingerprint=12345 \
  --fingerprint-platform=windows \
  --fingerprint-brand=Chrome \
  --fingerprint-brand-version=134.0.6998.165 \
  --fingerprint-hardware-concurrency=8
```

## 重要注意事项

### 1. 备份原始代码

在部署前，建议备份原始的134.0.6998.165标签：

```bash
git tag backup-134.0.6998.165-original 134.0.6998.165
git push origin backup-134.0.6998.165-original
```

### 2. 兼容性检查

- 确保所有补丁都能正确应用
- 验证构建过程无错误
- 测试指纹防护功能正常工作

### 3. 文档更新

更新相关文档：

```bash
# 更新README.md中的版本信息
# 更新构建说明
# 添加重构说明
```

## 回滚方案

如果部署出现问题，可以快速回滚：

```bash
# 回滚到原始版本
git reset --hard backup-134.0.6998.165-original
git tag -f 134.0.6998.165
git push origin 134.0.6998.165 --force
```

## 后续维护

### 1. 监控构建状态

- 定期检查构建是否成功
- 监控指纹防护功能是否正常
- 收集用户反馈

### 2. 版本更新

当需要更新到新的Chromium版本时：

- 检查补丁兼容性
- 更新GPU信息数据库
- 测试所有指纹防护功能

### 3. 问题处理

如果发现问题：

- 检查构建日志
- 验证补丁应用状态
- 必要时进行热修复

## 联系信息

如有问题，请通过以下方式联系：

- GitHub Issues: https://github.com/fjlmcm/chromium/issues
- 项目维护者: [维护者信息]

## 许可证

本项目遵循与Chromium相同的BSD-3-Clause许可证。 