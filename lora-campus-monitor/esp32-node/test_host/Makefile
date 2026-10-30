CXX ?= g++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -Werror -O1
INCLUDES = -I../include
SOURCES = test_main.cpp ../src/packet_builder.cpp ../src/data_filter.cpp ../src/scheduler.cpp

run: run_tests
	./run_tests

run_tests: $(SOURCES) ../include/packet_builder.h ../include/data_filter.h ../include/scheduler.h
	$(CXX) $(CXXFLAGS) $(INCLUDES) $(SOURCES) -lm -o $@

clean:
	rm -f run_tests

.PHONY: run clean
