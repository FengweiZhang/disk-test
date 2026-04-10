MPYTHON ?= /home/zfw/miniconda3/envs/ub/bin/python
CONFIG ?= config_quick.json

.PHONY: run plot install

run:
	sudo $(MPYTHON) main.py -c $(CONFIG)

plot:
	sudo $(MPYTHON) -m nvme_test.plot $(ARGS)

install:
	$(MPYTHON) -m pip install -r requirements.txt
