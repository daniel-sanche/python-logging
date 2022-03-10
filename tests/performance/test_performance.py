# Copyright 2016 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import pytest
import unittest
import math
import mock
import time
import itertools

import pandas as pd
from tqdm import tqdm

import google.cloud.logging
from google.cloud.logging_v2.services.logging_service_v2 import LoggingServiceV2Client
from google.cloud.logging_v2.services.logging_service_v2.transports import LoggingServiceV2Transport
from google.cloud.logging_v2._http import _LoggingAPI
import google.auth.credentials
from google.cloud.logging_v2 import _gapic


class MockGRPCTransport(LoggingServiceV2Transport):
    """
    Mock for grpc transport.
    Instead of sending logs to server, introduce artificial delay
    """
    def __init__(self, latency=0.1, **kwargs):
        self.latency = latency
        self._wrapped_methods = {self.write_log_entries: self.write_log_entries}

    def write_log_entries(self, *args, **kwargs):
        time.sleep(self.latency)

class MockHttpAPI(_LoggingAPI):
    """
    Mock for http API implementation.
    Instead of sending logs to server, introduce artificial delay
    """
    def __init__(self, client, latency=0.1):
        self._client = client
        self.api_request = lambda **kwargs: time.sleep(latency)

def _make_client(mock_network=True, use_grpc=True, mock_latency=0.01):
    """
    Create and return a new test client to manage writing logs
    Can optionally create a real GCP client, or a mock client with artificial network calls
    Can choose between grpc and http client implementations
    """
    start = time.perf_counter()
    if not mock_network:
        # use a real client
        client = google.cloud.logging.Client(_use_grpc=use_grpc)
    elif use_grpc:
        # create a mock grpc client
        mock_transport = MockGRPCTransport(latency=mock_latency)
        gapic_client = LoggingServiceV2Client(transport=mock_transport)
        handwritten_client = mock.Mock()
        api = _gapic._LoggingAPI(gapic_client, handwritten_client)
        creds = mock.Mock(spec=google.auth.credentials.Credentials)
        client = google.cloud.logging.Client(project="my-project",  credentials=creds)
        client._logging_api = api
    else:
        # create a mock http client
        creds = mock.Mock(spec=google.auth.credentials.Credentials)
        client = google.cloud.logging.Client(project="my-project",  credentials=creds)
        mock_http = MockHttpAPI(client, latency=mock_latency)
        client._logging_api = mock_http
    logger = client.logger(name="test_logger")
    end = time.perf_counter()
    return client, logger, end-start

def logger_log(logger, num_logs=100, payload_size=10, json_payload=False):
    # build pay load
    log_payload = "message "
    log_payload = log_payload * math.ceil(payload_size / len(log_payload))
    log_payload = log_payload[:payload_size]
    if json_payload:
        log_payload = {"key": log_payload}
    # start code under test
    start = time.perf_counter()
    # create logs
    for i in range(num_logs):
        logger.log(log_payload)
    end = time.perf_counter()
    return end - start

def batch_log(logger, num_logs=100, payload_size=10, json_payload=False):
    # build pay load
    log_payload = "message "
    log_payload = log_payload * math.ceil(payload_size / len(log_payload))
    log_payload = log_payload[:payload_size]
    if json_payload:
        log_payload = {"key": log_payload}
    # start code under test
    start = time.perf_counter()
    # create logs
    with logger.batch() as batch:
        for i in range(num_logs):
            batch.log(log_payload)
    end = time.perf_counter()
    return end - start

def benchmark():
    results = []
    with tqdm(total=(2*2*2)+2, leave=False) as pbar:
        grpc_client, grpc_logger, time = _make_client(mock_network=True, use_grpc=True)
        results.append({"description": f"grpc client setup", "exec_time": time})
        http_client, http_logger, time = _make_client(mock_network=True, use_grpc=False)
        results.append({"description": f"http client setup", "exec_time": time})
        for fn_str, fn_val in [('logger.log', logger_log), ('batch.log', batch_log)]:
            for network_str, network_val in [('grpc', grpc_logger), ('http', http_logger)]:
                for payload_str, payload_val in [('json', True), ('text', False)]:
                    time = fn_val(network_val, payload_size=1000000, json_payload=payload_val)
                    results.append({"description": f"{fn_str} over {network_str} with {payload_str} payload", "exec_time": time})
                    pbar.update(1)
    # print results dataframe
    benchmark_df = pd.DataFrame(results)
    print(benchmark_df)
    total_time = benchmark_df['exec_time'].sum()
    print(f"Total Benchmark Time: {total_time:.1f}s")

class TestPerformance(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        print("Done")


    def test_benchmark(self):
        benchmark()

    # def test_test(self):

    #     client = _make_client(mock_network=True, use_grpc=False, mock_latency=0)
    #     logger_log(client)

