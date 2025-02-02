# Copyright 2023 The MediaPipe Authors.
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
"""Face stylizer dataset library."""

from typing import Sequence
import logging
import os

import tensorflow as tf

from mediapipe.model_maker.python.core.data import classification_dataset
from mediapipe.model_maker.python.vision.face_stylizer import constants
from mediapipe.python._framework_bindings import image as image_module
from mediapipe.tasks.python.core import base_options as base_options_module
from mediapipe.tasks.python.vision import face_aligner


def _preprocess_face_dataset(
    all_image_paths: Sequence[str],
) -> Sequence[tf.Tensor]:
  """Preprocess face image dataset by aligning the face."""
  path = constants.FACE_ALIGNER_TASK_FILES.get_path()
  base_options = base_options_module.BaseOptions(model_asset_path=path)
  options = face_aligner.FaceAlignerOptions(base_options=base_options)
  aligner = face_aligner.FaceAligner.create_from_options(options)

  preprocessed_images = []
  for path in all_image_paths:
    tf.compat.v1.logging.info('Preprocess image %s', path)
    image = image_module.Image.create_from_file(path)
    aligned_image = aligner.align(image)
    aligned_image_tensor = tf.convert_to_tensor(aligned_image.numpy_view())
    preprocessed_images.append(aligned_image_tensor)

  return preprocessed_images


# TODO: Change to a unlabeled dataset if it makes sense.
class Dataset(classification_dataset.ClassificationDataset):
  """Dataset library for face stylizer fine tuning."""

  @classmethod
  def from_folder(
      cls, dirname: str
  ) -> classification_dataset.ClassificationDataset:
    """Loads images from the given directory.

    The style image dataset directory is expected to contain one subdirectory
    whose name represents the label of the style. There can be one or multiple
    images of the same style in that subdirectory. Supported input image formats
    include 'jpg', 'jpeg', 'png'.

    Args:
      dirname: Name of the directory containing the image files.

    Returns:
      Dataset containing images and labels and other related info.
    Raises:
      ValueError: if the input data directory is empty.
    """
    data_root = os.path.abspath(dirname)

    # Assumes the image data of the same label are in the same subdirectory,
    # gets image path and label names.
    all_image_paths = list(tf.io.gfile.glob(data_root + r'/*/*'))
    all_image_size = len(all_image_paths)
    if all_image_size == 0:
      raise ValueError('Invalid input data directory')
    if not any(
        fname.endswith(('.jpg', '.jpeg', '.png')) for fname in all_image_paths
    ):
      raise ValueError('No images found under given directory')

    image_data = _preprocess_face_dataset(all_image_paths)
    label_names = sorted(
        name
        for name in os.listdir(data_root)
        if os.path.isdir(os.path.join(data_root, name))
    )
    all_label_size = len(label_names)
    index_by_label = dict(
        (name, index) for index, name in enumerate(label_names)
    )
    # Get the style label from the subdirectory name.
    all_image_labels = [
        index_by_label[os.path.basename(os.path.dirname(path))]
        for path in all_image_paths
    ]

    image_ds = tf.data.Dataset.from_tensor_slices(image_data)

    # Load label
    label_ds = tf.data.Dataset.from_tensor_slices(
        tf.cast(all_image_labels, tf.int64)
    )

    # Create a dataset of (image, label) pairs
    image_label_ds = tf.data.Dataset.zip((image_ds, label_ds))

    logging.info(
        'Load images dataset with size: %d, num_label: %d, labels: %s.',
        all_image_size,
        all_label_size,
        ', '.join(label_names),
    )
    return Dataset(
        dataset=image_label_ds, size=all_image_size, label_names=label_names
    )
