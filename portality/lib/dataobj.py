from portality.lib import dates
from copy import deepcopy
import locale, json

import inspect

#########################################################
## Data coerce functions

def to_unicode():
    def to_utf8_unicode(val):
        if val is None:
            return None

        if isinstance(val, unicode):
            return val
        elif isinstance(val, basestring):
            try:
                return val.decode("utf8", "strict")
            except UnicodeDecodeError:
                raise ValueError(u"Could not decode string")
        else:
            return unicode(val)

    return to_utf8_unicode

def to_int():
    def intify(val):
        if val is None:
            return None

        # strip any characters that are outside the ascii range - they won't make up the int anyway
        # and this will get rid of things like strange currency marks
        if isinstance(val, unicode):
            val = val.encode("ascii", errors="ignore")

        # try the straight cast
        try:
            return int(val)
        except ValueError:
            pass

        # could have commas in it, so try stripping them
        try:
            return int(val.replace(",", ""))
        except ValueError:
            pass

        # try the locale-specific approach
        try:
            return locale.atoi(val)
        except ValueError:
            pass

        raise ValueError(u"Could not convert string to int: {x}".format(x=val))

    return intify

def to_float():
    def floatify(val):
        if val is None:
            return None

        # strip any characters that are outside the ascii range - they won't make up the float anyway
        # and this will get rid of things like strange currency marks
        if isinstance(val, unicode):
            val = val.encode("ascii", errors="ignore")

        # try the straight cast
        try:
            return float(val)
        except ValueError:
            pass

        # could have commas in it, so try stripping them
        try:
            return float(val.replace(",", ""))
        except ValueError:
            pass

        # try the locale-specific approach
        try:
            return locale.atof(val)
        except ValueError:
            pass

        raise ValueError(u"Could not convert string to float: {x}".format(x=val))

    return floatify

def date_str(in_format=None, out_format=None):
    def datify(val):
        if val is None:
            return None
        return dates.reformat(val, in_format=in_format, out_format=out_format)

    return datify

def to_datestamp(in_format=None):
    def stampify(val):
        if val is None:
            return None
        return dates.parse(val, format=in_format)

    return stampify

def to_isolang(output_format=None):
    """
    :param output_format: format from input source to putput.  Must be one of:
        * alpha3
        * alt3
        * alpha2
        * name
        * fr
    Can be a list in order of preference, too
    :return:
    """
    # delayed import, since we may not always want to load the whole dataset for a dataobj
    from portality.lib import isolang as dataset

    # sort out the output format list
    if output_format is None:
        output_format = ["alpha3"]
    if not isinstance(output_format, list):
        output_format = [output_format]

    def isolang(val):
        if val is None:
            return None
        l = dataset.find(val)
        for f in output_format:
            v = l.get(f)
            if v is None or v == "":
                continue
            return v

    return isolang

def to_url(val):
    if val is None:
        return None
    # FIXME: implement
    return val

def to_bool():
    def boolify(val):
        """Conservative boolean cast - don't cast lists and objects to True, just existing booleans and strings."""
        if val is None:
            return None
        if val is True or val is False:
            return val

        if isinstance(val, basestring):
            if val.lower() == 'true':
                return True
            elif val.lower() == 'false':
                return False
            raise ValueError(u"Could not convert string {val} to boolean. Expecting string to either say 'true' or 'false' (not case-sensitive).".format(val=val))

        raise ValueError(u"Could not convert {val} to boolean. Expect either boolean or string.".format(val=val))

    return boolify

############################################################

############################################################
## The core data object which manages all the interactions
## with the underlying data member variable

class DataSchemaException(Exception):
    pass

class DataObj(object):
    """
    Class which stores data according to a defined structure and provides
    validation on setting any attribute. Recursive (if any of its attributes
    contain an object or a list of objects, these will be wrapped in a
    DataObj themselves and any actions delegated to the new DataObj).
    """

    _coerce = {
        "unicode": to_unicode(),
        "utcdatetime": date_str(),
        "integer": to_int(),
        "float": to_float(),
        "isolang": to_isolang(),
        "url": to_url,
        "bool": to_bool()
    }

    _RESERVED_ATTR_NAMES = [
        '__class__',
        '__delattr__',
        '__dict__',
        '__doc__',
        '__format__',
        '__getattribute__',
        '__hash__',
        '__init__',
        '__members__',
        '__methods__',
        '__module__',
        '__new__',
        '__reduce__',
        '__reduce_ex__',
        '__repr__',
        '__setattr__',
        '__sizeof__',
        '__str__',
        '__subclasshook__',
        '__weakref__',
        '_add_struct',
        '_struct',
        '_type',
        '_silent_drop_extra_fields',
        '_RESERVED_ATTR_NAMES',
        '_coerce',
        '_data'
    ]

    def __init__(self, raw=None, _struct=None, _type=None, _silent_drop_extra_fields=False):
        assert isinstance(raw, dict), "The raw data passed in must be iterable as a dict."

        self._silent_drop_extra_fields = _silent_drop_extra_fields

        if _type:
            self._type = _type

        if not self._type:
            raise ValueError("Can't create DataObj without a type")

        if _struct:
            self._struct = _struct
        else:
            self._struct = {}

        self._data = {}
        for k, v in raw.iteritems():
            setattr(self, k, v)

        # restructure the object based on the struct if required
        # ET note to self and not isinstance(self.data, DataObj) ?
        # if self.struct is not None:
        #     self.data = self.construct(self.data, self.struct, self.coerce, drop_extra_fields=drop_extra_fields)

    def __getattribute__(self, name):
        # If this attribute is not already set in the internal data
        # but it's supposed to be an object (not primitive type)
        # then set it to an empty DataObj with the struct it's
        # supposed to have. That way if the caller is chaining
        # a setter to [name] we'll keep a pointer to the right object.
        # E.g. the caller does:
        # j = JournalDO()
        # j.bibjson.title = 'atitle'
        # This function will be called with name == "bibjson".
        # If we didn't keep track of an empty bibjson object,
        # the .title would be set on an object we would no longer have
        # a handle on.

        # attrs used in creating a DataObj should behave as they usually
        # would in Python
        if name in object.__getattribute__(self, '_RESERVED_ATTR_NAMES'):
            return object.__getattribute__(self, name)

        if object.__getattribute__(self, '_data').get(name) is None:
        # the requested attribute is not present in the data already

            if name in object.__getattribute__(self, '_struct').get('objects', []):
                object.__getattribute__(self, '_data')[name] = DataObj(raw={}, _struct=object.__getattribute__(self, '_struct')['structs'][name], _type=name)
            elif name in object.__getattribute__(self, '_struct').get('lists', {}):
                object.__getattribute__(self, '_data')[name] = []
            elif name in object.__getattribute__(self, '_struct').get('fields', {}):
            # it's a primitive field that isn't set
                try:
                    # if there is a default set in the struct, return it
                    if object.__getattribute__(self, '_struct')['fields'][name].get("default") is not None:
                        return object.__getattribute__(self, '_struct')['fields'][name]["default"]
                    # else cast a None
                    return object.__getattribute__(self, '_coerce')[object.__getattribute__(self, '_struct')['fields'][name]['coerce']](None)
                except ValueError:
                    raise AttributeError('{name} is not set'.format(name=name))
            else:
            # it's not a valid attribute of this object
                raise AttributeError('{name} is not an attribute of {type}'.format(name=name, type=object.__getattribute__(self, '_type')))

        # the requested attribute is in the internal data
        return object.__getattribute__(self, '_data')[name]

    # TODO note that on any serialisation each field that is not required and its contents are not truthy
    # (unless they are False) or only an empty data object, those fields should not be serialised.
    # TODO add .empty to data objects

    def __setattr__(self, name, value):
        # If what we're trying to set is an object itself,
        # pass it on to its own DataObj.
        # If it's a primitive, coerce it into the defined type.
        # If what we're trying to set is not in the struct, bail.

        # attrs used in creating a DataObj should behave as they usually
        # would in Python
        if name in object.__getattribute__(self, '_RESERVED_ATTR_NAMES'):
            return object.__setattr__(self, name, value)

        # it's another object, in which case we need to recurse
        if name in self._struct.get('objects', {}):
            self._data[name] = DataObj(raw=value, _struct=self._struct['structs'][name], _type=name, _silent_drop_extra_fields=self._silent_drop_extra_fields)

        # it's a list - what we do depends on if it contains simple fields or objects (recurse if latter)
        if name in self._struct.get('lists', {}):
            if not isinstance(value, list):
                raise ValueError('The "{name}" attribute of this data object is a list. Please supply a list as the value. Current value: {value}'.format(name=name, value=value))

            self._data[name] = []
            for i in value:
                try:
                    if self._struct['lists'][name]['contains'] == 'object':
                        coerced_i = DataObj(raw=i, _struct=self._struct['structs'][name], _type=name, _silent_drop_extra_fields=self._silent_drop_extra_fields)
                    elif self._struct['lists'][name]['contains'] == 'field':
                        coerced_i = self._coerce[self._struct['lists'][name]['coerce']](value)
                    else:
                        raise DataStructureException("Data object struct definition error: Don't understand how to interpret struct for list '{name}'. Only allowing 'contains':'object' and 'contains':'field'.".format(name=name))
                except KeyError as e:
                    if e.message == 'contains':
                        raise DataSchemaException("No information in struct provided on what {0} contains".format(name))
                    else:
                        raise DataSchemaException("Problem while setting {0}: KeyError for {1}".format(name, e.message))
                self._data[name].append(coerced_i)

        # it's a normal field, just set it with coercion
        elif name in self._struct.get('fields', {}):
            try:
                self._data[name] = self._coerce[self._struct['fields'][name]['coerce']](value)
            except KeyError as e:
                if e.message == 'coerce':
                    raise DataSchemaException("No information in struct provided on how to coerce {0}".format(name))
                else:
                    raise DataSchemaException("Problem while setting {0}: KeyError for {1}".format(name, e.message))


        # not an allowed attribute
        else:
            if not self._silent_drop_extra_fields:
                raise AttributeError('{name} is not an attribute of {type}'.format(name=name, type=self._type))
            return False  # still indicate it couldn't be set, more silently
        return True
        
    def _add_struct(self, struct):
        if hasattr(self, "_struct"):
            self._struct = construct_merge(self._struct, struct)
        else:
            self._struct = struct

## Data structure coercion

class DataStructureException(Exception):
    pass


def construct_merge(target, source):
    merged = deepcopy(target)

    for field, instructions in source.get("fields", {}).iteritems():
        if "fields" not in merged:
            merged["fields"] = {}
        if field not in merged["fields"]:
            merged["fields"][field] = deepcopy(instructions)

    for obj in source.get("objects", []):
        if "objects" not in merged:
            merged["objects"] = []
        if obj not in merged["objects"]:
            merged["objects"].append(obj)

    for field, instructions in source.get("lists", {}).iteritems():
        if "lists" not in merged:
            merged["lists"] = {}
        if field not in merged["lists"]:
            merged["lists"][field] = deepcopy(instructions)

    for r in source.get("required", []):
        if "required" not in merged:
            merged["required"] = []
        if r not in merged["required"]:
            merged["required"].append(r)

    for field, struct in source.get("structs", {}).iteritems():
        if "structs" not in merged:
            merged["structs"] = {}
        if field not in merged["structs"]:
            merged["structs"][field] = deepcopy(struct)

    return merged


############################################################
## Unit test support

def test_dataobj(obj, fields_and_values):
    """
    Test a dataobj to make sure that the getters and setters you have specified
    are working correctly.

    Provide it a data object and a list of fields with the values to set and the expected return values (if required):

    {
        "key" : ("set value", "get value")
    }

    If you provide only the set value, then the get value will be required to be the same as the set value in the test

    {
        "key" : "set value"
    }

    :param obj:
    :param fields_and_values:
    :return:
    """
    for k, valtup in fields_and_values.iteritems():
        if not isinstance(valtup, tuple):
            valtup = (valtup,)
        set_val = valtup[0]
        try:
            setattr(obj, k, set_val)
        except AttributeError:
            assert False, u"Unable to set attribute {x} with value {y}".format(x=k, y=set_val)

    for k, valtup in fields_and_values.iteritems():
        if not isinstance(valtup, tuple):
            valtup = (valtup,)
        get_val = valtup[0]
        if len(valtup) > 1:
            get_val = valtup[1]
        val = getattr(obj, k)
        assert val == get_val, ("Problem get-ting attribute", k, val, get_val)