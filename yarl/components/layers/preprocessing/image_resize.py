# Copyright 2018 The YARL-Project, All Rights Reserved.
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

from yarl import get_backend
from yarl.utils.util import get_rank
from yarl.components.layers.preprocessing import PreprocessLayer


if get_backend() == "tf":
    import tensorflow as tf


class ImageResize(PreprocessLayer):
    """
    Resizes one or more images to a new size without touching the color channel.
    """
    def __init__(self, width, height, scope="image-resize", **kwargs):
        """
        Args:
            width (int): The new width.
            height (int): The new height.
        """
        super(ImageResize, self).__init__(scope=scope, **kwargs)
        self.width = width
        self.height = height

    def check_input_spaces(self, input_spaces, action_space):
        super(ImageResize, self).check_input_spaces(input_spaces, action_space)
        in_space = input_spaces["apply"][0]

        # Store the mapped output Spaces (per flat key).
        for k, v in in_space.flatten().items():
            # Do some sanity checking.
            rank = in_space.rank
            assert rank == 2 or rank == 3, \
                "ERROR: Given image's rank (which is {}{}, not counting batch rank) must be either 2 or 3!".\
                format(rank, ("" if k == "" else " for key '{}'".format(k)))
            shape = list(v.shape)
            shape[0] = self.width
            shape[1] = self.height
            self.output_spaces[k] = v.__class__(shape=tuple(shape), add_batch_rank=v.has_batch_rank)

    def _graph_fn_apply(self, images):
        """
        Images come in with either a batch dimension or not.
        However, this
        """
        if self.backend == "python" or get_backend() == "python":
            import cv2
            return cv2.resize(images, dsize=(self.width, self.height))  # interpolation=cv2.BILINEAR
        elif get_backend() == "tf":
            return tf.image.resize_images(images=images, size=(self.width, self.height))

