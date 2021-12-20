from types import SimpleNamespace


class NestedNamespace(SimpleNamespace):
  def __init__(self, dictionary, **kwargs):
    super().__init__(**kwargs)
    for key, value in dictionary.items():
      self.__setattr__(key, self.__get_entry__(value))

  def __getattr__(self, key):
    return None

  def __get_entry__(self, value):
    if isinstance(value, dict):
      return NestedNamespace(value)
    elif isinstance(value, list):
      return [self.__get_entry__(item) for item in value]
    else:
      return value

  def to_dict(self):
    return self.__dict__
