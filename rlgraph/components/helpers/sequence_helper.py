# Copyright 2018 The RLgraph authors. All Rights Reserved.
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

from rlgraph import get_backend
from rlgraph.components import Component
from rlgraph.utils.decorators import rlgraph_api

if get_backend() == "tf":
    import tensorflow as tf
elif get_backend() == "pytorch":
    import torch


class SequenceHelper(Component):
    """
    A helper Component that helps prepare sequences.
    """

    def __init__(self, scope="sequence-helper", **kwargs):
        super(SequenceHelper, self).__init__(scope=scope, **kwargs)

    @rlgraph_api
    def _graph_fn_calc_sequence_lengths(self, sequence_indices):
        """
        Computes sequence lengths for a tensor containing sequence indices, where 1 indicates start
        of a new sequence.
        Args:
            sequence_indices (DataOp): Indices denoting sequences, e.g. terminal values.
        Returns:
            Sequence lengths.
        """
        if get_backend() == "tf":
            # TensorArray:
            elems = tf.shape(input=sequence_indices)[0]
            sequence_lengths = tf.TensorArray(
                dtype=tf.int32,
                infer_shape=False,
                size=1,
                dynamic_size=True,
                clear_after_read=False
            )

            def update(write_index, sequence_array, length):
                # Write to index, increase
                sequence_array = sequence_array.write(write_index, length)
                return sequence_array, write_index + 1, 0

            def insert_body(index, length, sequence_lengths, write_index):
                length += 1

                # Update tensor array, reset length to 0.
                sequence_lengths, write_index, length = tf.cond(
                    pred=tf.equal(sequence_indices[index], 1),
                    true_fn=lambda: update(write_index, sequence_lengths, length),
                    false_fn=lambda: (sequence_lengths, write_index, length)
                )
                return index + 1, length, sequence_lengths, write_index

            def cond(index, length, sequence_lengths, write_index):
                return index < elems

            _, final_length, sequence_lengths, write_index = tf.while_loop(
                cond=cond,
                body=insert_body,
                loop_vars=[0, 0, sequence_lengths, 0],
                back_prop=False
            )
            # If the final element was terminal -> already included.
            sequence_lengths, _, _ = tf.cond(
                pred=tf.greater(final_length, 0),
                true_fn=lambda: update(write_index, sequence_lengths, final_length),
                false_fn=lambda: (sequence_lengths, write_index, final_length)
            )
            return sequence_lengths.stack()
        elif get_backend() == "pytorch":
            sequence_lengths = []
            length = 0
            for index in sequence_indices:
                length += 1
                if index == 1:
                    sequence_lengths.append(length)
                    length = 0
            # Append final sequence.
            if length > 0:
                sequence_lengths.append(length)
            return torch.tensor(sequence_lengths, dtype=torch.int32)

    @rlgraph_api(returns=2)
    def _graph_fn_calc_sequence_decays(self, sequence_indices, decay):
        """
        Computes decays for sequence indices, e.g. for generalized advantage estimation.
        That is, a sequence with terminals is used to compute for each subsequence the decay
        values and the length of the sequence.

        Example:
        decay = 0.5, sequence_indices = [0 0 1 0 1] will return lengths [3, 2] and
        decays [1 0.5 0.25 1 0.5] (decay^0, decay^1, ..decay^k) where k = sequence length for
        each sub-sequence.

        Args:
            sequence_indices (DataOp): Indices denoting sequences, e.g. terminal values.
            decay (float): Initial decay value to start sub-sequence with.

        Returns:
            Sequence lengths and their decays.
        """
        if get_backend() == "tf":
            elems = tf.shape(input=sequence_indices)[0]
            # TensorArray:
            sequence_lengths = tf.TensorArray(
                dtype=tf.int32,
                infer_shape=False,
                size=1,
                dynamic_size=True,
                clear_after_read=False
            )
            decays = tf.TensorArray(
                dtype=tf.float32,
                infer_shape=False,
                size=1,
                dynamic_size=True,
                clear_after_read=False
            )

            def update(write_index, sequence_array, length):
                # Write to index, increase
                sequence_array = sequence_array.write(write_index, length)
                return sequence_array, write_index + 1, 0

            def insert_body(index, length, sequence_lengths, write_index, decays):
                # Decay is based on length, so val = decay^length
                decay_val = tf.pow(x=decay, y=tf.cast(length, dtype=tf.float32))

                # Write decay val into array.
                decays = decays.write(index, decay_val)
                length += 1

                # Update tensor array, reset length to 0.
                sequence_lengths, write_index, length = tf.cond(
                    pred=tf.equal(sequence_indices[index], 1),
                    true_fn=lambda: update(write_index, sequence_lengths, length),
                    false_fn=lambda: (sequence_lengths, write_index, length)
                )
                return index + 1, length, sequence_lengths, write_index, decays

            def cond(index, length, sequence_lengths, write_index, decays):
                return index < elems

            index, final_length, sequence_lengths, write_index, decays = tf.while_loop(
                cond=cond,
                body=insert_body,
                loop_vars=[0, 0, sequence_lengths, 0, decays],
                back_prop=False
            )

            # If the final element was terminal -> already included.
            # Decays need no updating because we just wrote them always.
            sequence_lengths, _, _ = tf.cond(
                pred=tf.greater(final_length, 0),
                true_fn=lambda: update(write_index, sequence_lengths, final_length),
                false_fn=lambda: (sequence_lengths, write_index, final_length)
            )
            return tf.stop_gradient(sequence_lengths.stack()), tf.stop_gradient(decays.stack())
        elif get_backend() == "pytorch":
            sequence_lengths = []
            decays = []

            length = 0
            for index in sequence_indices:
                # Compute decay based on sequence length.
                decays.append(pow(decay, length))
                length += 1
                if index == 1:
                    sequence_lengths.append(length)
                    length = 0

            # Append final sequence.
            if length > 0:
                sequence_lengths.append(length)
            return torch.tensor(sequence_lengths, dtype=torch.int32),\
                   torch.tensor(decays, dtype=torch.int32)


