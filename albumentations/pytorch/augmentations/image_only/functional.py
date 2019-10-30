import torch
import kornia as K

from functools import wraps


MAX_VALUES_BY_DTYPE = {torch.uint8: 255, torch.float32: 1.0, torch.float64: 1.0}


def clip(img, dtype, maxval):
    return torch.clamp(img, 0, maxval).type(dtype)


def clipped(func):
    @wraps(func)
    def wrapped_function(img, *args, **kwargs):
        dtype = img.dtype
        maxval = MAX_VALUES_BY_DTYPE.get(dtype, 1.0)
        return clip(func(img, *args, **kwargs), dtype, maxval)

    return wrapped_function


def from_float(img, dtype, max_value=None):
    if max_value is None:
        try:
            max_value = MAX_VALUES_BY_DTYPE[dtype]
        except KeyError:
            raise RuntimeError(
                "Can't infer the maximum value for dtype {}. You need to specify the maximum value manually by "
                "passing the max_value argument".format(dtype)
            )
    return clip(img * max_value, dtype, max_value)


def to_float(img, dtype, max_value=None):
    if max_value is None:
        try:
            max_value = MAX_VALUES_BY_DTYPE[img.dtype]
        except KeyError:
            raise RuntimeError(
                "Can't infer the maximum value for dtype {}. You need to specify the maximum value manually by "
                "passing the max_value argument".format(img.dtype)
            )
    return img.type(dtype) / max_value


def cutout(img, holes, fill_value=0):
    # Make a copy of the input image since we don't want to modify it directly
    img = img.clone()
    for x1, y1, x2, y2 in holes:
        img[:, y1:y2, x1:x2] = fill_value
    return img


def _rbg_to_hls_float(img):
    img = K.rgb_to_hls(img)
    img[0] *= 360
    return img


@clipped
def _rbg_to_hls_uint8(img):
    img = K.rgb_to_hls(img.float() / 255)
    img[0] *= 180
    img[1:] *= 255
    return img


def rgb_to_hls(img):
    if img.dtype in [torch.float32, torch.float64]:
        return _rbg_to_hls_float(img)
    elif img.dtype == torch.uint8:
        return _rbg_to_hls_uint8(img)

    raise ValueError("rbg_to_hls support only uint8, float32 and float64 dtypes. Got: {}".format(img.dtype))


@clipped
def _hls_to_rgb_uint8(img):
    img = img.float()
    img[0] /= 180
    img[1:] /= 255

    img = K.hls_to_rgb(img)
    img *= 255
    return img


def _hls_to_rgb_float(img):
    img = img.clone()
    img[0] /= 360
    return K.hls_to_rgb(img)


def hls_to_rgb(img):
    if img.dtype in [torch.float32, torch.float64]:
        return _hls_to_rgb_float(img)
    elif img.dtype == torch.uint8:
        return _hls_to_rgb_uint8(img)

    raise ValueError("hls_to_rgb support only uint8, float32 and float64 dtypes. Got: {}".format(img.dtype))


def add_snow(img, snow_point, brightness_coeff):
    """Bleaches out pixels, imitation snow.

    From https://github.com/UjjwalSaxena/Automold--Road-Augmentation-Library

    Args:
        img (torch.Tensor): Image.
        snow_point: Number of show points.
        brightness_coeff: Brightness coefficient.

    Returns:
        numpy.ndarray: Image.

    """
    input_dtype = img.dtype
    needs_float = False

    snow_point *= 127.5  # = 255 / 2
    snow_point += 85  # = 255 / 3

    if input_dtype == torch.float32:
        img = from_float(img, torch.uint8)
        needs_float = True
    elif input_dtype not in (torch.uint8, torch.float32):
        raise ValueError("Unexpected dtype {} for RandomSnow augmentation".format(input_dtype))

    image_HLS = rgb_to_hls(img)

    image_HLS[1][image_HLS[1] < snow_point] *= brightness_coeff
    image_HLS[1] = clip(image_HLS[1], torch.uint8, 255)

    image_RGB = hls_to_rgb(image_HLS)

    if needs_float:
        image_RGB = to_float(image_RGB, torch.float32)

    return image_RGB


def normalize(img, mean, std):
    if mean.shape:
        mean = mean[..., :, None, None]
    if std.shape:
        std = std[..., :, None, None]

    denominator = torch.reciprocal(std)

    img = img.float()
    img -= mean
    img *= denominator
    return img
