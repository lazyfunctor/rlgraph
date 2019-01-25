# Copyright 2018/2019 The RLgraph authors. All Rights Reserved.
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
# ==============================================================================

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np

from rlgraph import get_backend
from rlgraph.components.layers.preprocessing import PreprocessLayer
from rlgraph.utils.decorators import rlgraph_api
from rlgraph.utils.util import SMALL_NUMBER

if get_backend() == "tf":
    import tensorflow as tf


class MovingStandardize(PreprocessLayer):
    """
    Standardizes inputs using a moving estimate of mean and std.
    """
    def __init__(self, scope="moving-standardize", **kwargs):
        super(MovingStandardize, self).__init__(scope=scope, **kwargs)
        self.sample_count = None

        # Current estimate of state mean.
        self.mean_est = None

        # Current estimate of sum of stds.
        self.std_sum_est = None
        self.output_spaces = None
        self.in_space = None

    def create_variables(self, input_spaces, action_space=None):
        in_space = input_spaces["preprocessing_inputs"]
        self.output_spaces = in_space
        self.in_space = in_space

        if self.backend == "python" or get_backend() == "python":
            self.sample_count = 0
            self.mean_est = np.zeros(in_space.shape)
            self.std_sum_est = np.zeros(in_space.shape)
        elif get_backend() == "tf":
            self.sample_count = self.get_variable(name="sample-count", dtype="float", initializer=0.0, trainable=False)
            self.mean_est = self.get_variable(
                name="mean-est", trainable=False, from_space=in_space,
                add_batch_rank=in_space.has_batch_rank)
            self.std_sum_est = self.get_variable(
                name="std-sum-est", trainable=False, from_space=in_space,
                add_batch_rank=in_space.has_batch_rank)

    @rlgraph_api
    def _graph_fn_reset(self):
        if self.backend == "python" or get_backend() == "python" or get_backend() == "pytorch":
            self.sample_count = 0
            self.mean_est = np.zeros(self.in_space.shape)
            self.std_sum_est = np.zeros(self.in_space.shape)
        elif get_backend() == "tf":
            return tf.variables_initializer([self.sample_count, self.mean_est, self.std_sum_est])

    @rlgraph_api
    def _graph_fn_apply(self, preprocessing_inputs):
        if self.backend == "python" or get_backend() == "python" or get_backend() == "pytorch":
            # https://www.johndcook.com/blog/standard_deviation/
            preprocessing_inputs = np.asarray(preprocessing_inputs)
            self.sample_count += 1
            if self.sample_count == 1:
                self.mean_est = preprocessing_inputs
            else:
                update = preprocessing_inputs - self.mean_est
                self.mean_est += update / self.sample_count
                self.std_sum_est += update * update * (self.sample_count - 1) / self.sample_count

            # Subtract mean.
            result = preprocessing_inputs - self.mean_est

            # Estimate variance via sum of variance.
            if self.sample_count > 1:
                var_estimate = self.std_sum_est / (self.sample_count - 1)
            else:
                var_estimate = np.square(self.mean_est)
            std = np.sqrt(var_estimate) + SMALL_NUMBER

            return result / std

        elif get_backend() == "tf":
            assignments = [tf.assign_add(ref=self.sample_count, value=1.0)]
            with tf.control_dependencies(assignments):
                # 1. Update vars
                assignments = []
                update = preprocessing_inputs - self.mean_est
                mean_update = tf.cond(
                    pred=self.sample_count > 1.0,
                    false_fn=lambda: self.mean_est,
                    true_fn=lambda: tf.reduce_sum(update, axis=0)
                )
                var_update = update * update * (self.sample_count - 1) / self.sample_count
                assignments.append(tf.assign_add(ref=self.mean_est, value=mean_update))
                assignments.append(tf.assign_add(ref=self.std_sum_est, value=var_update))

            with tf.control_dependencies(assignments):
                # 2. Compute var estimate after update.
                var_estimate = tf.cond(
                    pred=self.sample_count > 1,
                    false_fn=lambda: tf.square(x=self.mean_est),
                    true_fn=lambda: self.std_sum_est / (self.sample_count - 1)
                )
                result = preprocessing_inputs - self.mean_est
                std = tf.sqrt(x=var_estimate) + SMALL_NUMBER

                return result / std