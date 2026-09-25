# Host (macOS/Linux) build of the RSDKv3 sprite-manifest tool (PS1 port, docs/28 phase 1).
# The engine's own bytecode loader + script VM run each stage's object startups on the host.
ENGINE = ../../RSDKv3
CXX ?= clang++
CXXFLAGS = -std=c++17 -O1 -g -DRETRO_PS1_HOST_TOOL -DRETRO_USE_MOD_LOADER=0 -I$(ENGINE) -Wno-everything
SRCS = main.cpp host_stubs.cpp $(ENGINE)/Script.cpp $(ENGINE)/Reader.cpp $(ENGINE)/String.cpp \
       $(ENGINE)/Object.cpp $(ENGINE)/Animation.cpp $(ENGINE)/Math.cpp

rsdkmanifest: $(SRCS) $(wildcard $(ENGINE)/*.hpp)
	$(CXX) $(CXXFLAGS) -o $@ $(SRCS)

clean:
	rm -rf rsdkmanifest rsdkmanifest.dSYM
.PHONY: clean
