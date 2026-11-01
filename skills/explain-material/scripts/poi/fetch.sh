#!/usr/bin/env bash
# 下载 Apache POI 依赖并编译逐页渲染器。
# 只在需要把 .ppt 渲染成图片时才用得到；不跑这个，ingest.py 会退回纯文字提取。
set -e
cd "$(dirname "$0")"

MIRROR="${POI_MIRROR:-https://maven.aliyun.com/repository/public}"
FALLBACK="https://repo1.maven.org/maven2"

fetch() {  # fetch <path-under-maven-root> <filename>
  local path="$1" name="$2"
  if [ -s "$name" ]; then echo "skip $name"; return; fi
  echo "get $name"
  curl -fsSL "$MIRROR/$path" -o "$name" || curl -fsSL "$FALLBACK/$path" -o "$name"
}

fetch org/apache/poi/poi/5.2.5/poi-5.2.5.jar poi.jar
fetch org/apache/poi/poi-scratchpad/5.2.5/poi-scratchpad-5.2.5.jar poi-scratchpad.jar
fetch commons-io/commons-io/2.15.1/commons-io-2.15.1.jar commons-io.jar
fetch commons-codec/commons-codec/1.16.0/commons-codec-1.16.0.jar commons-codec.jar
fetch org/apache/commons/commons-collections4/4.4/commons-collections4-4.4.jar collections4.jar
fetch org/apache/logging/log4j/log4j-api/2.21.1/log4j-api-2.21.1.jar log4j-api.jar
fetch com/zaxxer/SparseBitSet/1.3/SparseBitSet-1.3.jar sparsebitset.jar

CP="poi.jar:poi-scratchpad.jar:commons-io.jar:commons-codec.jar:collections4.jar:log4j-api.jar:sparsebitset.jar"
javac -cp "$CP" RenderPpt.java
echo "ok: $(ls *.jar | wc -l) jars + RenderPpt.class"
