.PHONY: help run submodules
REPO_NAME ?= aws-ocp
VENV_NAME?=venv
VENV_ACTIVATE=. $(VENV_NAME)/bin/activate
PYTHON=${VENV_NAME}/bin/python3
PYTHON3 := $(shell python3 -V 2>&1)
FUNCTIONS=GenerateIgnitionFiles DeployCF

submodules:
	git submodule init
	git submodule update
	#cd submodules/quickstart-linux-bastion && git submodule init && git submodule update 
	#cd submodules/quickstart-amazon-eks && git submodule init && git submodule update 

help:
	@echo   "make test  : executes taskcat"

create:
	aws cloudformation create-stack --stack-name test --template-body file://$(pwd)/templates/aws-ocp-student-env.template.yaml --parameters $(cat .ignore/params) --capabilities CAPABILITY_IAM

delete:
	aws cloudformation delete-stack --stack-name test

.ONESHELL:
test: lint create_zips
	taskcat test run -n

lint:
	time taskcat lint

public_repo:
	taskcat -c $(REPO_NAME)/ci/config.yml -u
	#https://taskcat-tag-quickstart-jfrog-artifactory-c2fa9d34.s3-us-west-2.amazonaws.com/quickstart-jfrog-artifactory/templates/jfrog-artifactory-ec2-master.template
	#curl https://taskcat-tag-quickstart-jfrog-artifactory-7008506c.s3-us-west-2.amazonaws.com/quickstart-jfrog-artifactory/templates/jfrog-artifactory-ec2-master.template

create_zips:
	for folder in `ls functions/source/` ; do \
		if [ ! -d functions/packages/$$folder ]; then \
			mkdir functions/packages/$$folder ; \
		fi ;\
		cd functions/source/$$folder && \
		ls && \
		zip -r ../../packages/$$folder/lambda.zip * && \
		cd ../../../ ; \
	done

verify:
ifdef PYTHON3
	@echo "python3 Found, continuing."
else
	@echo "please install python3"
	exit 1
endif


venv:
	@make verify
	python3 -m venv $(VENV_NAME)/
	${VENV_ACTIVATE}
	${PYTHON} -m pip install -U pip
	${PYTHON} -m pip install -r requirements.txt

run_lambda: venv
	export SSH_KEY='${SSH_KEY}' && \
	export PULL_SECRET='${PULL_SECRET}' && \
	${VENV_ACTIVATE} && \
	cd functions/source/GenerateIgnitionFiles/ && \
	python-lambda-local -f lambda_handler lambda_function.py ../../tests/ignition_files_env_variables.json -t 300


# Used from other projects, commenting out for reference
#get_public_dns:
#	aws elb describe-load-balancers | jq '.LoadBalancerDescriptions[]| .CanonicalHostedZoneName'
#
#get_bastion_ip:
#	aws ec2 describe-instances | jq '.[] | select(.[].Instances[].Tags[].Value == "LinuxBastion") '
