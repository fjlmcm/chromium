# 浏览器指纹保护功能

本文档介绍了指纹保护功能的使用方法和技术细节。

## 什么是浏览器指纹？

浏览器指纹是网站通过收集您浏览器和设备的独特特征来识别您的一种方式，即使您禁用了Cookie或使用隐私浏览模式。这些特征包括但不限于：

- 字体列表
- Canvas 绘图特征
- WebGL 渲染信息
- 屏幕分辨率和颜色深度
- 已安装的插件
- 用户代理字符串
- 时区
- 硬件并发性（CPU核心数）

## 指纹保护功能

本浏览器通过以下方式保护您的隐私：

1. **添加微小噪声到几何测量中**：对`getClientRects()`和`getBoundingClientRect()`的返回值添加细微的变化
2. **字体保护**：保留常见系统字体，同时增加一些渲染参数的随机性
3. **Canvas指纹保护**：对Canvas API的测量和图像数据添加微小随机变化
4. **用户代理伪装**：允许自定义UA字符串
5. **硬件并发性保护**：允许自定义返回的CPU核心数

## 使用方法

### 基本用法

启用所有指纹保护功能，只需添加`--fingerprint=<数字>`参数：

```
chromium.exe --fingerprint=12345
```

这里的数字可以是任意整数，但建议使用随机数。数字不同会产生不同的"指纹"，所以为了保持一致性，请在每次启动浏览器时使用相同的数字。

### 高级选项

除了基本的`--fingerprint`参数外，还可以使用以下参数进一步定制：

- `--fingerprint-platform="Windows"` - 指定操作系统类型
- `--fingerprint-platform-version="10.0"` - 指定操作系统版本
- `--fingerprint-brand="Chrome"` - 指定浏览器品牌
- `--fingerprint-brand-version="116.0.0.0"` - 指定浏览器版本
- `--fingerprint-hardware-concurrency=4` - 指定CPU核心数

例如：

```
chromium.exe --fingerprint=12345 --fingerprint-platform="Windows" --fingerprint-platform-version="10.0" --fingerprint-hardware-concurrency=4
```

## 技术细节

### 字体保护

字体保护机制不再完全屏蔽非标准字体，而是允许所有系统字体，但在渲染时添加微小的随机变化。这样可以避免网站检测出您使用了字体伪装技术，同时仍然保护您的隐私。

### Canvas保护

当网站使用Canvas API尝试获取图像数据时，会添加对少量像素的微小变化，而不是显著改变整个图像。这种方法在保护隐私的同时保持了良好的用户体验。

### 客户端矩形保护

当网站调用`getClientRects()`或`getBoundingClientRect()`时，返回的坐标和尺寸会添加非常小的变化（约万分之一），这足以改变指纹但几乎不会影响布局和渲染。

## 隐私与兼容性平衡

本浏览器的指纹保护功能经过精心设计，在保护隐私和保持网站兼容性之间取得平衡。与完全禁用或显著改变功能的方法不同，我们采用了"微小随机化"策略，使网站仍然可用，但跟踪您变得更加困难。

## 测试您的保护

您可以访问以下网站测试指纹保护效果：

- https://coveryourtracks.eff.org/
- https://browserleaks.com/
- https://fingerprintjs.github.io/fingerprintjs/

注意：即使启用了所有保护，也不能保证100%匿名。指纹保护是一项复杂的挑战，需要不断改进。 