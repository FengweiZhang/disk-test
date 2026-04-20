MPYTHON ?= /home/zfw/miniconda3/envs/ub/bin/python
CONFIG ?= config_quick.json
PER_DEVICE_COMPARE_CONFIG ?= config_per_device_compare.json

.PHONY: run plot install

run:
	sudo $(MPYTHON) main.py -c $(CONFIG)

per-device-compare:
	sudo $(MPYTHON) main.py -c $(PER_DEVICE_COMPARE_CONFIG)

plot:
	sudo $(MPYTHON) -m nvme_test.plot $(ARGS)

install:
	$(MPYTHON) -m pip install -r requirements.txt
