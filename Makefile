MPYTHON ?= /home/zfw/nvme-over-ub/vllm/.venv/bin/python
CONFIG ?= config_quick.json
PER_DEVICE_COMPARE_CONFIG ?= config_per_device_compare.json
CONFIG_DIR ?= configs

.PHONY: run plot install

run:
	sudo $(MPYTHON) main.py -c $(CONFIG_DIR)/config_write_gpu0.json

per-device-compare:
	sudo $(MPYTHON) main.py -c $(CONFIG_DIR)/$(PER_DEVICE_COMPARE_CONFIG)

gpu0:
	sudo $(MPYTHON) main.py -c $(CONFIG_DIR)/config_per_device_compare_gpu0.json

gpu1:
	sudo $(MPYTHON) main.py -c $(CONFIG_DIR)/config_per_device_compare_gpu1.json

gpu-all:
	sudo $(MPYTHON) main.py -c $(CONFIG_DIR)/config_per_device_compare_all.json

plot:
	sudo $(MPYTHON) -m nvme_test.plot $(ARGS)

install:
	$(MPYTHON) -m pip install -r requirements.txt
