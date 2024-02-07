SYNAPSE_DIR:=.
SETUP_DIR=..

synapse:
	docker compose -f ${SYNAPSE_DIR}/docker-compose.yml up -d --force-recreate --build

synapse2:
	docker compose -f ${SYNAPSE_DIR}/docker-compose.synapse2.yml up -d --force-recreate --build

setup:
	cd ${SETUP_DIR} && make setup

setup2:
	cd ${SETUP_DIR} && make setup ENV=dev2 TEST_HOMESERVER_URL=http://localhost:8010 SYNAPSE_DOCKER_LABEL=org.homeserver2=true
