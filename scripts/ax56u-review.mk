# Additional explicit targets, loaded after the vendor top-level Makefile.
# Run from release/src-rt-5.02axhnd.675x with BUILD_NAME=RT-AX56U PROFILE=947622GW.
.PHONY: ax56u-router-clean
ax56u-router-clean:
	$(MAKE) -C router clean
