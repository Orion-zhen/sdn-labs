# Self-learning Switch

## 环境搭建

由于我使用的系统是[ArchLinux](https://archlinux.org), 所以我更倾向于在本地搭建所需环境, 而不是使用封装好的镜像. 这样也能加深我对实验的理解

经过实践, 阅读相关文档和源码, 我了解到:

1. `ryu`不能运行在`Python 3.10`版本及以上, 因为`Python 3.10`删除和变化了许多属性和方法, 导致`ryu`无法运行. 例如`TypeError: cannot set 'is_timeout' attribute of immutable type 'TimeoutError`
2. `ryu`自己的依赖项版本有误, `eventlet`模块需要手动降级成`0.30.2`, 否则会有诸如`ImportError: cannot import name 'ALREADY_HANDLED' from 'eventlet.wsgi'`的错误

在尝试多种解决方案后, 我决定自行构建docker容器来运行:

```dockerfile
FROM ubuntu:20.04
LABEL maintainer="Orion-zhen"
RUN apt update && apt install -y python3 python3-pip python-is-python3 && pip3 install ryu && pip3 install eventlet==0.30.2
EXPOSE 6633 8080
WORKDIR /work
COPY ./ /work/
```
