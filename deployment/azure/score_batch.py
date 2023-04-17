import json
import numpy as np
import os
import tensorflow as tf
import io
import base64
import gzip
import nibabel as nib
import skimage
import logging

def dice_metrics(y_true, y_pred, axis=(1, 2, 3, 4)):
    """Calculate Dice similarity between labels and predictions.
    Dice similarity is in [0, 1], where 1 is perfect overlap and 0 is no
    overlap. If both labels and predictions are empty (e.g., all background),
    then Dice similarity is 1.
    If we assume the inputs are rank 5 [`(batch, x, y, z, classes)`], then an
    axis parameter of `(1, 2, 3)` will result in a tensor that contains a Dice
    score for every class in every item in the batch. The shape of this tensor
    will be `(batch, classes)`. If the inputs only have one class (e.g., binary
    segmentation), then an axis parameter of `(1, 2, 3, 4)` should be used.
    This will result in a tensor of shape `(batch,)`, where every value is the
    Dice similarity for that prediction.
    Implemented according to https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4533825/#Equ6
    Returns
    -------
    Tensor of Dice similarities.
    Citations
    ---------
    Taha AA, Hanbury A. Metrics for evaluating 3D medical image segmentation:
        analysis, selection, and tool. BMC Med Imaging. 2015;15:29. Published 2015
        Aug 12. doi:10.1186/s12880-015-0068-x
    """
    y_pred = tf.convert_to_tensor(y_pred)
    y_true = tf.cast(y_true, y_pred.dtype)
    eps = tf.keras.backend.epsilon()

    intersection = tf.reduce_sum(y_true * y_pred, axis=axis)
    summation = tf.reduce_sum(y_true, axis=axis) + tf.reduce_sum(y_pred, axis=axis)
    return (2 * intersection + eps) / (summation + eps)

def jaccard_metrics(y_true, y_pred, axis=(1, 2, 3, 4)):
    """Calculate Jaccard similarity between labels and predictions.
    Jaccard similarity is in [0, 1], where 1 is perfect overlap and 0 is no
    overlap. If both labels and predictions are empty (e.g., all background),
    then Jaccard similarity is 1.
    If we assume the inputs are rank 5 [`(batch, x, y, z, classes)`], then an
    axis parameter of `(1, 2, 3)` will result in a tensor that contains a Jaccard
    score for every class in every item in the batch. The shape of this tensor
    will be `(batch, classes)`. If the inputs only have one class (e.g., binary
    segmentation), then an axis parameter of `(1, 2, 3, 4)` should be used.
    This will result in a tensor of shape `(batch,)`, where every value is the
    Jaccard similarity for that prediction.
    Implemented according to https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4533825/#Equ7
    Returns
    -------
    Tensor of Jaccard similarities.
    Citations
    ---------
    Taha AA, Hanbury A. Metrics for evaluating 3D medical image segmentation:
        analysis, selection, and tool. BMC Med Imaging. 2015;15:29. Published 2015
        Aug 12. doi:10.1186/s12880-015-0068-x
    """
    y_pred = tf.convert_to_tensor(y_pred)
    y_true = tf.cast(y_true, y_pred.dtype)
    eps = tf.keras.backend.epsilon()

    intersection = tf.reduce_sum(y_true * y_pred, axis=axis)
    union = tf.reduce_sum(y_true, axis=axis) + tf.reduce_sum(y_pred, axis=axis)
    return (intersection + eps) / (union - intersection + eps)

def jaccard_loss(y_true, y_pred, axis=(1, 2, 3, 4)):
    return 1.0 - jaccard_metrics(y_true=y_true, y_pred=y_pred, axis=axis)

def _transform_and_predict(
    model, x, block_shape, rotation, translation=[0, 0, 0], verbose=False
):
    """Predict on rigidly transformed features.
    The rigid transformation is applied to the volumes prior to prediction, and
    the prediced labels are transformed with the inverse warp, so that they are
    in the same space.
    Parameters
    ----------
    model: `tf.keras.Model`, model used for prediction.
    x: 3D array, volume of features.
    block_shape: tuple of length 3, shape of non-overlapping blocks to take
        from the features. This also corresponds to the input of the model, not
        including the batch or channel dimensions.
    rotation: tuple of length 3, rotation angle in radians in each dimension.
    translation: tuple of length 3, units of translation in each dimension.
    verbose: bool, whether to print progress bar.
    Returns
    -------
    Array of predictions with the same shape and in the same space as the
    original input features.
    """

    x = np.asarray(x).astype(np.float32)
    affine = get_affine(x.shape, rotation=rotation, translation=translation)
    inverse_affine = tf.linalg.inv(affine)
    x_warped = warp(x, affine, order=1)

    x_warped_blocks = to_blocks_numpy(x_warped, block_shape)
    x_warped_blocks = x_warped_blocks[..., np.newaxis]  # add grayscale channel
    x_warped_blocks = standardize_numpy(x_warped_blocks)
    y = model.predict(x_warped_blocks, batch_size=1, verbose=verbose)

    n_classes = y.shape[-1]
    if n_classes == 1:
        y = y.squeeze(-1)
    else:
        # Usually, the argmax would be taken to get the class membership of
        # each voxel, but if we get hard values, then we cannot average
        # multiple predictions.
        raise ValueError(
            "This function is not compatible with multi-class predictions."
        )

    y = from_blocks_numpy(y, x.shape)
    y = warp(y, inverse_affine, order=0).numpy()

    return 

# %%
def _to_blocks_perm(ndims):
    """Build permutation vector to go from volume to blocks.
    For 3D input, perm will be (0, 2, 4, 1, 3, 5). For 4D input (i.e. 3D volume
    with channels), perm will be (0, 2, 4, 6, 1, 3, 5, 7). Higher dimensional
    input is possible here.
    Parameters
    ----------
    ndims : int
        Number of dimensions in blocks and volumes.
    Returns
    -------
    perm : tuple
        The permutation vector
    """
    perm = np.empty(2 * ndims, dtype=int)
    perm[:ndims] = np.arange(0, ndims * 2, 2)
    perm[ndims:] = np.arange(1, ndims * 2, 2)
    return tuple(perm)

# %%
def _from_blocks_perm(ndims):
    """Build permutation vector to go from blocks to volume.
    For 3D input, perm will be (0, 3, 1, 4, 2, 5). For 4D input (i.e. 3D volume
    with channels), perm will be (0, 4, 1, 5, 2, 6, 3, 7). Higher dimensional
    input is possible here.
    Parameters
    ----------
    ndims : int
        Number of dimensions in blocks and volumes.
    Returns
    -------
    perm : tuple
        The permutation vector
    """
    perm = np.empty(2 * ndims, dtype=int)
    perm[::2] = np.arange(ndims)
    perm[1::2] = np.arange(ndims, 2 * ndims)
    return tuple(perm)

def standardize_numpy(a):
    """Standard score array.
    Implements `(x - mean(x)) / stdev(x)`.
    Parameters
    ----------
    x: array, values to standardize.
    Returns
    -------
    Array of standardized values. Output has mean 0 and standard deviation 1.
    """
    a = np.asarray(a)
    return (a - a.mean()) / a.std()

def to_blocks_numpy(a, block_shape):
    """Return new array of non-overlapping blocks of shape `block_shape` from
    array `a`.
    For the reverse of this function (blocks to array), see `from_blocks_numpy`.
    Parameters
    ----------
    a: array-like, 3D or 4D array to block
    block_shape: tuple of len 3 or 4, shape of non-overlapping blocks.
    Returns
    -------
    Rank 4 or 5 array with shape `(N, *block_shape)`, where N is the number of
    blocks.
    """
    a = np.asarray(a)
    orig_shape = np.asarray(a.shape)

    if a.ndim not in [3, 4]:
        raise ValueError("This function only supports 3D or 4D arrays.")

    if isinstance(block_shape, int):
        block_shape = tuple(list([block_shape]) * 3)

    if len(block_shape) not in [3, 4]:
        raise ValueError("block_shape must have three values.")

    blocks = orig_shape // block_shape
    inter_shape = tuple(e for tup in zip(blocks, block_shape) for e in tup)
    new_shape = (-1,) + block_shape
    perm = _to_blocks_perm(ndims=len(block_shape))

    return a.reshape(inter_shape).transpose(perm).reshape(new_shape)

def from_blocks_numpy(a, output_shape):
    """Combine 4D array of non-overlapping blocks `a` into 3D array of shape
    `output_shape`.
    For the reverse of this function, see `to_blocks_numpy`.
    Parameters
    ----------
    a: array-like, 4D or 5D array of blocks with shape (N, *block_shape), where
        N is the number of blocks.
    output_shape: tuple of len 3 or 4, shape of the combined array.
    Returns
    -------
    Rank 3 array with shape `output_shape`.
    """
    a = np.asarray(a)

    if a.ndim not in [4, 5]:
        raise ValueError("This function only works for 4D or 5D arrays.")
    if len(output_shape) not in [3, 4]:
        raise ValueError("output_shape must have three or four values.")

    n_blocks = a.shape[0]
    block_shape = a.shape[1:]
    ncbrt = np.cbrt(n_blocks).round(6)
    if not ncbrt.is_integer():
        raise ValueError("Cubed root of number of blocks is not an integer")
    ncbrt = int(ncbrt)
    perm = _from_blocks_perm(ndims=len(block_shape))
    intershape = (ncbrt, ncbrt, ncbrt, *block_shape)
    # Allow channels (i.e. 4D)
    if len(block_shape) == 4:
        intershape = (ncbrt, ncbrt, ncbrt, 1, *block_shape)

    return a.reshape(intershape).transpose(perm).reshape(output_shape)

def predict(
    img,
    block_shape=(128, 128, 128),
    resize_features_to=(256, 256, 256),
    threshold=0.3,
    largest_label=False,
    rotate_and_predict=False,
    verbose=False,
):
    if not verbose:
        os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
        tf.get_logger().setLevel(logging.ERROR)

    data = img.get_fdata(caching="unchanged")
    data = data.astype(np.float32)
    x, affine = data, img.affine
    if x.ndim != 3:
        raise ValueError("Input volume must be rank 3, got rank {}".format(x.ndim))
    original_shape = x.shape
    required_shape = resize_features_to
    must_resize = False
    if x.shape != required_shape:
        must_resize = True
        if verbose:
            print(
                "Resizing volume from shape {} to shape {}".format(
                    x.shape, required_shape
                )
            )
        x = skimage.transform.resize(
            x,
            output_shape=required_shape,
            order=1,  # linear
            mode="constant",
            preserve_range=True,
            anti_aliasing=False,
        )

    x = standardize_numpy(x)
    x_blocks = to_blocks_numpy(x, block_shape=block_shape)
    x_blocks = x_blocks[..., None]  # Add grayscale channel.

    if verbose:
        print("Predicting ...")
    try:
        y_blocks = model.predict(x_blocks, batch_size=1, verbose=verbose)
    except Exception:
        print(click.style("ERROR: prediction failed. See error trace.", fg="red"))
        raise

    # Collapse the last dimension, depending on number of output classes.
    is_binary_prediction = y_blocks.shape[-1] == 1
    if is_binary_prediction:
        y_blocks = y_blocks.squeeze(-1)
    else:
        y_blocks = y_blocks.argmax(-1)

    y = from_blocks_numpy(y_blocks, x.shape)

    # Rotate the volume, predict, undo the rotation, and average with original
    # prediction.
    if rotate_and_predict:
        if not is_binary_prediction:
            raise ValueError("Cannot transform and predict on multi-class output.")
        if verbose:
            print("Predicting on rotated volume ...")
        y_other = transform_and_predict(
            model=model,
            x=x,
            block_shape=block_shape,
            rotation=[np.pi / 4, np.pi / 4, 0],
            translation=[0, 0, 0],
            verbose=verbose,
        )
        if verbose:
            print("Averaging predictions ...")
        y = np.mean([y, y_other], axis=0)

    if is_binary_prediction:
        if threshold <= 0 or threshold >= 1:
            raise ValueError("Threshold must be in (0, 1).")
        y = y > threshold

    if must_resize:
        if verbose:
            print(
                "Resizing volume from shape {} to shape {}".format(
                    y.shape, original_shape
                )
            )
        y = skimage.transform.resize(
            y,
            output_shape=original_shape,
            order=0,  # nearest neighbor
            mode="constant",
            preserve_range=True,
            anti_aliasing=False,
        )

    if largest_label:
        if not is_binary_prediction:
            raise ValueError(
                "Removing all labels except the largest is only allowed with binary"
                " prediction."
            )
        if verbose:
            print("Removing all labels except largest ...")
        labels, n_labels = skimage.measure.label(y, return_num=True)
        # Do not consider 0 values.
        d = {(labels == label).sum(): label for label in range(1, n_labels + 1)}
        largest_label = d[max(d.keys())]
        if verbose:
            print(
                "Zeroed {} region(s) not contiguous with largest label.".format(
                    n_labels - 2
                )
            )
        y = (labels == largest_label).astype(np.int32)

    imgout = nib.Nifti1Image(y.astype(np.int32), affine=affine)
    return imgout

def init():
    global model
    global output_path
    # tf.keras.backend.set_learning_phase(0) 
    model_path = os.path.join(os.getenv('AZUREML_MODEL_DIR'), 'model.h5')
    model = tf.keras.models.load_model(model_path, custom_objects={'jaccard_loss': jaccard_loss, 'dice_coef': dice_metrics})
    output_path = os.environ["AZUREML_BI_OUTPUT_PATH"]

    # conv_kwds = {
    #     "kernel_size": (3, 3, 3),
    #     "activation": None,
    #     "padding": "same"
    # }

    # conv_transpose_kwds = {
    #     "kernel_size": (2, 2, 2),
    #     "strides": 2,
    #     "padding": "same"
    # }
    # n_base_filters = 16
    # inputs = tf.keras.layers.Input(shape=(128,128,128,1), batch_size=None)
    # x = tf.keras.layers.Conv3D(n_base_filters, **conv_kwds)(inputs)
    # x = tf.keras.layers.Activation("sigmoid")(x)

    # model2=tf.keras.Model(inputs=inputs, outputs=x, name="unet")
    # model=model2

def run(batch):
    outputfilenames = []
    for filepath in batch:
        img = nib.load(filepath)
        imgout = predict(img, verbose=1)
        base, filename = os.path.split(filepath)
        outputfilename = os.path.join(output_path, filename)
        outputfilenames.append(outputfilename)
        nib.save(imgout, outputfilename)
    return outputfilenames
        
    