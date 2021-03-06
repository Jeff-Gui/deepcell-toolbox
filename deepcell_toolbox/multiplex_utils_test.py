# Copyright 2016-2021 The Van Valen Lab at the California Institute of
# Technology (Caltech), with support from the Paul Allen Family Foundation,
# Google, & National Institutes of Health (NIH) under Grant U24CA224309-01.
# All rights reserved.
#
# Licensed under a modified Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.github.com/vanvalenlab/deepcell-tf/LICENSE
#
# The Work provided may be used for non-commercial academic purposes only.
# For any other use of the Work, including commercial use, please contact:
# vanvalenlab@gmail.com
#
# Neither the name of Caltech nor the names of its contributors may be used
# to endorse or promote products derived from this software without specific
# prior written permission.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Tests for multiplex_utils.py"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np

import numpy as np

import pytest

from deepcell_toolbox.multiplex_utils import format_output_multiplex
from deepcell_toolbox.multiplex_utils import multiplex_postprocess
from deepcell_toolbox.multiplex_utils import multiplex_preprocess


def test_multiplex_preprocess():
    height, width = 300, 300
    img = np.random.randint(0, 100, (height, width))

    # make rank 4 (batch, X, y, channel)
    img = np.expand_dims(img, axis=0)
    img = np.expand_dims(img, axis=-1)

    # single bright spot
    img[0, 200, 200, 0] = 5000

    # histogram normalized
    processed = multiplex_preprocess(img)
    assert (processed <= 1).all() and (processed >= -1).all()

    # maxima is no longer significantly greater than rest of image
    new_spot_val = processed[0, 200, 200, 0]
    processed[0, 200, 200, 0] = 0.5
    next_max_val = np.max(processed)

    # difference between bright spot and next greatest value is essentially nothing
    assert np.round(new_spot_val / next_max_val, 1) == 1

    # histogram normalization without thresholding
    processed_hist = multiplex_preprocess(img, threshold=False)
    assert (processed_hist <= 1).all() and (processed_hist >= -1).all()

    new_spot_val = processed_hist[0, 200, 200, 0]
    processed_hist[0, 200, 200, 0] = 0.5
    next_max_val = np.max(processed_hist)
    assert np.round(new_spot_val / next_max_val, 1) > 1

    # thresholding without histogram normalization
    processed_thresh = multiplex_preprocess(img, normalize=False)
    assert not (processed_thresh <= 1).all()

    new_spot_val = processed_thresh[0, 200, 200, 0]
    processed_thresh[0, 200, 200, 0] = 0.5
    next_max_val = np.max(processed_thresh)
    assert np.round(new_spot_val / next_max_val, 1) == 1

    # no change to image
    not_processed = multiplex_preprocess(img, normalize=False, threshold=False)
    assert np.all(not_processed == img)


def test_multiplex_postprocess(mocker):
    # create dict, with each image having a different constant value
    base_array = np.ones((1, 20, 20, 1))

    whole_cell_list = [base_array * mult for mult in range(1, 3)]
    whole_cell_dict = {'inner-distance': whole_cell_list[0],
                       'pixelwise-interior': whole_cell_list[1]}

    nuclear_list = [base_array * mult for mult in range(3, 5)]
    nuclear_dict = {'inner-distance': nuclear_list[0],
                    'pixelwise-interior': nuclear_list[1]}

    model_output = {'whole-cell': whole_cell_dict, 'nuclear': nuclear_dict}

    # whole cell predictions only
    whole_cell = multiplex_postprocess(model_output=model_output,
                                       compartment='whole-cell')
    assert whole_cell.shape == (1, 20, 20, 1)

    # nuclear predictions only
    nuclear = multiplex_postprocess(model_output=model_output,
                                    compartment='nuclear')
    assert nuclear.shape == (1, 20, 20, 1)

    # both whole-cell and nuclear predictions
    both = multiplex_postprocess(model_output=model_output,
                                 compartment='both')
    assert both.shape == (1, 20, 20, 2)

    # make sure correct arrays are being passed to helper function
    def mock_deep_watershed_mibi(model_output):
        pixelwise_interior_vals = model_output['pixelwise-interior']
        return pixelwise_interior_vals

    mocker.patch('deepcell_toolbox.multiplex_utils.deep_watershed_mibi',
                 mock_deep_watershed_mibi)

    # whole cell predictions only
    whole_cell_mocked = multiplex_postprocess(model_output=model_output,
                                              compartment='whole-cell')

    assert np.array_equal(whole_cell_mocked, whole_cell_dict['pixelwise-interior'])

    # nuclear predictions only
    whole_cell_mocked = multiplex_postprocess(model_output=model_output,
                                              compartment='nuclear')

    assert np.array_equal(whole_cell_mocked, nuclear_dict['pixelwise-interior'])

    with pytest.raises(ValueError):
        whole_cell = multiplex_postprocess(model_output=model_output,
                                           compartment='invalid')


def test_format_output_multiplex():

    # create output list, each with a different constant value across image
    base_array = np.ones((1, 20, 20, 1))

    whole_cell_list = [base_array * mult for mult in range(1, 5)]
    whole_cell_list = [whole_cell_list[0],
                       np.concatenate(whole_cell_list[1:4], axis=-1)]

    # create output list for nuclear predictions
    nuclear_list = [img * 2 for img in whole_cell_list]

    combined_list = whole_cell_list + nuclear_list

    output = format_output_multiplex(combined_list)

    assert set(output.keys()) == {'whole-cell', 'nuclear'}

    assert np.array_equal(output['whole-cell']['inner-distance'], base_array)
    assert np.array_equal(output['nuclear']['inner-distance'], base_array * 2)

    assert np.array_equal(output['whole-cell']['pixelwise-interior'], base_array * 3)
    assert np.array_equal(output['nuclear']['pixelwise-interior'], base_array * 6)

    with pytest.raises(ValueError):
        output = format_output_multiplex(combined_list[:3])
