BASE ?= http://127.0.0.1:17777
API_PREFIX ?= /v1
STRICT_DELTA ?= 1
CLEANUP ?= 0
BUNDLE_ON_FAIL ?= 1

.PHONY: test-mvp test-mvp-plus
test-mvp:
	BASE=$(BASE) API_PREFIX=$(API_PREFIX) ./scripts/test_mvp.sh

test-mvp-plus:
	BASE=$(BASE) API_PREFIX=$(API_PREFIX) STRICT_DELTA=$(STRICT_DELTA) CLEANUP=$(CLEANUP) BUNDLE_ON_FAIL=$(BUNDLE_ON_FAIL) ./scripts/test_mvp_plus.sh
