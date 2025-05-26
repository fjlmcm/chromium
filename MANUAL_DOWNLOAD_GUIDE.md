# 手动下载Chromium源码指南

如果自动克隆失败，可以尝试以下手动下载方法：

## 方法1: 使用官方tar包

```bash
# 1. 创建下载目录
mkdir -p build/download_cache

# 2. 手动下载tar包 (约2GB)
# 访问: https://commondatastorage.googleapis.com/chromium-browser-official/
# 下载: chromium-134.0.6998.165-lite.tar.xz

# 3. 解压到正确位置
python utils/downloads.py unpack -c build/download_cache -i downloads.ini -- build/src
```

## 方法2: 使用GitHub镜像

```bash
# 1. 克隆GitHub镜像 (可能不是最新版本)
git clone --depth=2 -b 134.0.6998.165 https://github.com/chromium/chromium.git build/src

# 2. 如果标签不存在，使用主分支
git clone --depth=2 https://github.com/chromium/chromium.git build/src
cd build/src
git checkout -b 134.0.6998.165
```

## 方法3: 使用代理

```bash
# 设置HTTP代理 (替换为你的代理地址)
git config --global http.proxy http://proxy.example.com:8080
git config --global https.proxy https://proxy.example.com:8080

# 然后重新运行构建
python build.py
```

## 方法4: 分步下载

```bash
# 1. 只下载必要的文件
python utils/clone.py -o build/src --custom-config minimal.gclient

# 2. 手动下载大文件
# 访问Google Cloud Storage下载PGO配置文件等
```

## 网络优化设置

```bash
# 增加Git缓冲区
git config --global http.postBuffer 524288000
git config --global http.maxRequestBuffer 100M

# 设置超时
git config --global http.lowSpeedLimit 0
git config --global http.lowSpeedTime 999999

# 禁用SSL验证 (不推荐，仅在必要时使用)
git config --global http.sslVerify false
```

## 故障排除

1. **网络连接问题**: 尝试使用VPN或代理
2. **磁盘空间不足**: 确保至少有20GB可用空间
3. **权限问题**: 以管理员身份运行
4. **防火墙阻止**: 检查防火墙设置

## 联系支持

如果所有方法都失败，请：
1. 检查网络连接
2. 尝试在不同时间下载
3. 考虑使用预编译版本
