# PythonJS builtins
# by Amirouche Boubekki and Brett Hartshorn - copyright 2013
# License: "New BSD"


_PythonJS_UID = 0


with javascript:

	def __object_keys__(ob):
		'''
		notes:
			. Object.keys(ob) will not work because we create PythonJS objects using `Object.create(null)`
			. this is different from Object.keys because it traverses the prototype chain.
		'''
		arr = []
		JS('for (key in ob) { arr.push(key) }')
		return arr

	def __bind_property_descriptors__(o, klass):
		for name in klass.__properties__:
			desc = {enumerable:True}
			prop = klass.__properties__[ name ]
			if prop['get']:
				desc['get'] = __generate_getter__(klass, o, name)
			if prop['set']:
				desc['set'] = __generate_setter__(klass, o, name)

			Object.defineProperty( o, name, desc )

		for base in klass.__bases__:
			__bind_property_descriptors__(o, base)


	def __generate_getter__(klass, o, n):
		return lambda : klass.__properties__[ n ]['get']([o],{})
	def __generate_setter__(klass, o, n):
		return lambda v: klass.__properties__[ n ]['set']([o,v],{})


	def __sprintf(fmt, args):
		i = 0
		return JS("fmt.replace(/%((%)|s)/g, function (m) { return m[2] || args[i++] })")

	def create_class(class_name, parents, attrs, props):
		"""Create a PythonScript class"""
		if attrs.__metaclass__:
			metaclass = attrs.__metaclass__
			attrs.__metaclass__ = None
			return metaclass([class_name, parents, attrs])

		klass = Object.create(null)
		klass.__bases__ = parents
		klass.__name__ = class_name
		#klass.__dict__ = attrs
		klass.__unbound_methods__ = Object.create(null)
		klass.__all_method_names__ = []
		klass.__properties__ = props
		klass.__attributes__ = attrs
		for key in attrs:
			if typeof( attrs[key] ) == 'function':
				klass.__unbound_methods__[key] = attrs[key]
				klass.__all_method_names__.push( key )

			if key == '__getattribute__': continue
			klass[key] = attrs[key]

		## this is needed for fast lookup of property names in set_attribute ##
		klass.__setters__ = []
		klass.__getters__ = []
		for name in klass.__properties__:
			prop = klass.__properties__[name]
			klass.__getters__.push( name )
			if prop['set']:
				klass.__setters__.push( name )
		for base in klass.__bases__:
			Array.prototype.push.apply( klass.__getters__, base.__getters__ )
			Array.prototype.push.apply( klass.__setters__, base.__setters__ )
			Array.prototype.push.apply( klass.__all_method_names__, base.__all_method_names__ )


		def __call__():
			"""Create a PythonJS object"""
			object = Object.create(null)
			object.__class__ = klass
			## we need __dict__ so that __setattr__ can still set attributes using `old-style`: self.__dict__[n]=x
			Object.defineProperty(
				object, 
				'__dict__', 
				{enumerable:False, value:object, writeable:False, configurable:False}
			)


			has_getattribute = False
			has_getattr = False
			for name in klass.__all_method_names__:
				if name == '__getattribute__':
					has_getattribute = True
				elif name == '__getattr__':
					has_getattr = True
				else:
					wrapper = __get__(object, name)
					if not wrapper.is_wrapper:
						print 'RUNTIME ERROR: failed to get wrapper for:',name

			## to be safe the getters come after other methods are cached ##
			if has_getattr:
				__get__(object, '__getattr__')

			if has_getattribute:
				__get__(object, '__getattribute__')

			__bind_property_descriptors__(object, klass)

			if object.__init__:
				object.__init__.apply(this, arguments)

			return object

		__call__.pythonscript_function = True
		klass.__call__ = __call__
		return klass


def type(ob_or_class_name, bases=None, class_dict=None):
	'''
	type(object) -> the object's type
	type(name, bases, dict) -> a new type  ## broken? - TODO test
	'''
	with javascript:
		if bases is None and class_dict is None:
			return ob_or_class_name.__class__
		else:
			return create_class(ob_or_class_name, bases, class_dict)  ## TODO rename create_class to _pyjs_create_class

def hasattr(ob, attr, method=False):
	with javascript:
		#if method:
		#	return Object.hasOwnProperty.call(ob, attr)
		#elif Object.hasOwnProperty(ob, '__dict__'):
		#	return Object.hasOwnProperty.call(ob.__dict__, attr)
		#else:
		return Object.hasOwnProperty.call(ob, attr)

def getattr(ob, attr, property=False):
	with javascript:
		if property:
			prop = _get_upstream_property( ob.__class__, attr )
			if prop and prop['get']:
				return prop['get']( [ob], {} )
			else:
				print "ERROR: getattr property error", prop
		else:
			return __get__(ob, attr)  ## TODO rename to _pyjs_get_attribute

def setattr(ob, attr, value, property=False):
	with javascript:
		if property:
			prop = _get_upstream_property( ob.__class__, attr )
			if prop and prop['set']:
				prop['set']( [ob, value], {} )
			else:
				print "ERROR: setattr property error", prop
		else:
			set_attribute(ob, attr, value)

def issubclass(C, B):
	if C is B:
		return True
	with javascript: bases = C.__bases__  ## js-array
	i = 0
	while i < bases.length:
		if issubclass( bases[i], B ):
			return True
		i += 1
	return False

def isinstance( ob, klass):
	with javascript:
		if ob is None or ob is null:
			return False
		elif not Object.hasOwnProperty.call(ob, '__class__'):
			return False
		ob_class = ob.__class__
	if ob_class is None:
		return False
	else:
		return issubclass( ob_class, klass )



def int(a):
	with javascript:
		if instanceof(a, String):
			return window.parseInt(a)
		else:
			return Math.round(a)

def float(a):
	with javascript:
		if instanceof(a, String):
			return window.parseFloat(a)
		else:
			return a

def round(a, places):
	with javascript:
		b = '' + a
		if b.indexOf('.') == -1:
			return a
		else:
			c = b.split('.')
			x = c[0]
			y = c[1].substring(0, places)
			return parseFloat( x+'.'+y )


def str(s):
	return ''+s

def _setup_str_prototype():
	'''
	Extend JavaScript String.prototype with methods that implement the Python str API.
	The decorator @String.prototype.[name] assigns the function to the prototype,
	and ensures that the special 'this' variable will work.
	'''
	with javascript:

		@String.prototype.__contains__
		def func(a):
			if this.indexOf(a) == -1: return False
			else: return True

		@String.prototype.get
		def func(index):
			return this[ index ]

		@String.prototype.__iter__
		def func(self):
			with python:
				return Iterator(this, 0)

		@String.prototype.__getitem__
		def func(idx):
			return this[ idx ]

		@String.prototype.__len__
		def func():
			return this.length

		@String.prototype.__getslice__
		def func(start, stop, step):
			if start is None and stop is None and step == -1:
				return this.split('').reverse().join('')
			else:
				if stop < 0:
					stop = this.length + stop
				return this.substring(start, stop)

		@String.prototype.splitlines
		def func():
			return this.split('\n')

		@String.prototype.strip
		def func():
			return this.trim()  ## missing in IE8

		@String.prototype.startswith
		def func(a):
			if this.substring(0, a.length) == a:
				return True
			else:
				return False

		@String.prototype.endswith
		def func(a):
			if this.substring(this.length-a.length, this.length) == a:
				return True
			else:
				return False

		@String.prototype.join
		def func(a):
			out = ''
			if instanceof(a, Array):
				arr = a
			else:
				arr = a[...]
			i = 0
			for value in arr:
				out += value
				i += 1
				if i < arr.length:
					out += this
			return out

		@String.prototype.upper
		def func():
			return this.toUpperCase()

		@String.prototype.lower
		def func():
			return this.toLowerCase()

		@String.prototype.index
		def func(a):
			return this.indexOf(a)

		@String.prototype.isdigit
		def func():
			digits = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
			for char in this:
				if char in digits: pass
				else: return False
			return True

		## TODO - for now these are just dummy functions.
		@String.prototype.decode
		def func(encoding):
			return this
		@String.prototype.encode
		def func(encoding):
			return this


_setup_str_prototype()

def _setup_array_prototype():

	with javascript:

		@Array.prototype.__contains__
		def func(a):
			if this.indexOf(a) == -1: return False
			else: return True

		@Array.prototype.__len__
		def func():
			return this.length

		@Array.prototype.get
		def func(index):
			return this[ index ]

		@Array.prototype.__iter__
		def func(self):
			with python:
				return Iterator(this, 0)

		@Array.prototype.__getslice__
		def func(start, stop, step):
			if stop < 0:
				stop = this.length + stop
			return this.slice(start, stop)

		@Array.prototype.append
		def func(item):
			this.push( item )

		@Array.prototype.remove
		def func(item):
			index = this.indexOf( item )
			this.splice(index, 1)

		@Array.prototype.bisect
		def func(x, low, high):
			if low is None: low = 0
			if high is None: high = this.length
			while low < high:
				a = low+high
				mid = Math.floor(a/2)
				if x < this[mid]:
					high = mid
				else:
					low = mid + 1
			return low

		## set-like features ##
		## `-` operator
		@Array.prototype.difference
		def func(other):
			return this.filter( lambda i: other.indexOf(i)==-1)
		## `&` operator
		@Array.prototype.intersection
		def func(other):
			return this.filter( lambda i: other.indexOf(i)!=-1)
		## `<=` operator
		@Array.prototype.issubset
		def func(other):
			for item in this:
				if other.indexOf(item) == -1:
					return False
			return True

_setup_array_prototype()

def bisect(a, x, low=None, high=None):
	if isinstance(a, list):
		return a[...].bisect(x, low, high)
	else:
		return a.bisect(x, low, high)


def range(num, stop):
	"""Emulates Python's range function"""
	if stop is not None:
		i = num
		num = stop
	else:
		i = 0
	with javascript:
		arr = []
		while i < num:
			arr.push(i)
			i += 1
	return list( pointer=arr )

def xrange(num, stop):
	return range(num, stop)

class StopIteration:
	pass


def len(obj):
	return obj.__len__()


def next(obj):
	return obj.next()


def map(func, objs):
	with javascript: arr = []
	for ob in objs:
		v = func(ob)
		with javascript:
			arr.push( v )
	return list( pointer=arr )

def filter(func, objs):
	with javascript: arr = []
	for ob in objs:
		if func( ob ):
			with javascript:
				arr.push( ob )
	return list( pointer=arr )


def min( lst ):
	a = None
	for value in lst:
		if a is None: a = value
		elif value < a: a = value
	return a

def max( lst ):
	a = None
	for value in lst:
		if a is None: a = value
		elif value > a: a = value
	return a

def abs( num ):
	return JS('Math.abs(num)')

def ord( char ):
	return JS('char.charCodeAt(0)')

def chr( num ):
	return JS('String.fromCharCode(num)')

class Iterator:
	## rather than throwing an exception, it could be more optimized to have the iterator set a done flag,
	## and another downside is having the try/catch around this makes errors in in the loop go slient.
	def __init__(self, obj, index):
		self.obj = obj
		self.index = index
		self.length = len(obj)
		self.obj_get = obj.get  ## cache this for speed

	def next(self):
		## slow for looping over something that grows or shrinks while looping,
		## this conforms to standard Python, but it is slow, and probably not often needed.
		index = self.index
		length = len(self.obj)
		if index == length:
			raise StopIteration
		item = self.obj.get(self.index)
		self.index = self.index + 1
		return item

	def next_fast(self):
		with javascript:
			index = self.index
			self.index += 1
			return self.obj_get( [index], {} )


class tuple:
	def __init__(self, js_object=None, pointer=None):
		with javascript:
			if pointer:
				self[...] = pointer
			else:
				arr = []
				self[...] = arr

		if instanceof( js_object, Array ):
			for item in js_object:
				arr.push( item )

		elif js_object:

			if isinstance( js_object, array) or isinstance( js_object, tuple) or isinstance( js_object, list):
				for v in js_object:
					arr.push( v )
			else:
				raise TypeError



	def __getitem__(self, index):
		if index < 0:
			index = self[...].length + index
		with javascript:
			return self[...][index]


	def __iter__(self):
		return Iterator(self, 0)

	def __len__(self):
		with javascript:
			return self[...].length

	@property
	def length(self):
		with javascript:
			return self[...].length

	def index(self, obj):
		with javascript:
			return self[...].indexOf(obj)

	def count(self, obj):
		with javascript:
			a = 0
			for item in self[...]:
				if item == obj:
					a += 1
			return a


	def get(self, index): ## used by Iterator
		with javascript:
			return self[...][index]

	def __contains__(self, value):
		with javascript:
			if self[...].indexOf(value) == -1:
				return False
			else:
				return True


class list:

	def __init__(self, js_object=None, pointer=None):

		if pointer:
			self[...] = pointer  ## should be an Array

		else:
			with javascript:
				arr = []
				self[...] = arr

			if instanceof( js_object, Array ):
				for item in js_object:
					arr.push( item )

			elif js_object:

				if isinstance( js_object, array) or isinstance( js_object, tuple) or isinstance( js_object, list):
					for v in js_object:
						arr.push( v )
				else:
					raise TypeError

	@fastdef
	def __getitem__(self, index):
		if index < 0:
			index = self[...].length + index
		with javascript:
			return self[...][index]

	@fastdef
	def __setitem__(self, index, value):
		with javascript:
			self[...][ index ] = value

	def __getslice__(self, start, stop, step=None):
		with javascript: arr = self[...].__getslice__(start, stop)
		return list( pointer=arr )

	def append(self, obj):
		with javascript:
			self[...].push( obj )

	def extend(self, other):
		for obj in other:
			self.append(obj)

	def insert(self, index, obj):
		with javascript:
			self[...].splice(index, 0, obj)

	def remove(self, obj):
		index = self.index(obj)
		with javascript:
			self[...].splice(index, 1)

	def pop(self):
		with javascript:
			return self[...].pop()

	def index(self, obj):
		with javascript:
			return self[...].indexOf(obj)

	def count(self, obj):
		with javascript:
			a = 0
			for item in self[...]:
				if item == obj:
					a += 1
			return a

	def reverse(self):
		with javascript:
			self[...] = self[...].reverse()

	def shift(self):
		with javascript:
			return self[...].shift()

	def slice(self, start, end):
		with javascript:
			return self[...].slice(start, end)

	def __iter__(self):
		return Iterator(self, 0)

	def get(self, index):
		with javascript:
			return self[...][index]

	def set(self, index, value):
		with javascript:
			self[...][index] = value

	def __len__(self):
		with javascript:
			return self[...].length

	@property
	def length(self):
		with javascript:
			return self[...].length

	def __contains__(self, value):
		with javascript:
			if self[...].indexOf(value) == -1:
				return False
			else:
				return True

class dict:
	# http://stackoverflow.com/questions/10892322/javascript-hashtable-use-object-key
	# using a function as a key is allowed, but would waste memory because it gets converted to a string
	# http://stackoverflow.com/questions/10858632/are-functions-valid-keys-for-javascript-object-properties
	UID = 0
	def __init__(self, js_object=None):
		with javascript:
			self[...] = {}

		if js_object:
			if JS("js_object instanceof Array"):
				i = 0
				while i < js_object.length:
					JS('var key = js_object[i]["key"]')
					JS('var value = js_object[i]["value"]')
					self.set(key, value)
					i += 1

			elif isinstance(js_object, list):
				with javascript:
					for item in js_object[...]:
						key = item[...][0]
						value = item[...][1]
						self[...][ key ] = value
			else:  ## TODO - deprecate
				self[...] = js_object


	def get(self, key, _default=None):
		__dict = self[...]
		if JS("typeof(key) === 'object'"):
			JS('var uid = "@"+key.uid') ## gotcha - what if "@undefined" was in __dict ?
			if JS('uid in __dict'):
				return JS('__dict[uid]')
		elif JS("typeof(key) === 'function'"):
			JS('var uid = "@"+key.uid')
			if JS('uid in __dict'):
				return JS('__dict[uid]')
		else:
			if JS('key in __dict'):
				return JS('__dict[key]')

		return _default

	def set(self, key, value):
		global _PythonJS_UID

		__dict = self[...]
		if JS("typeof(key) === 'object'"):
			if JS("key.uid === undefined"):
				uid = _PythonJS_UID
				JS("key.uid = uid")
				_PythonJS_UID += 1
			JS('var uid = key.uid')
			JS('__dict["@"+uid] = value')
		elif JS("typeof(key) === 'function'"):
			if JS("key.uid === undefined"):
				uid = _PythonJS_UID
				JS("key.uid = uid")
				_PythonJS_UID += 1
			JS('var uid = key.uid')
			JS('__dict["@"+uid] = value')
		else:
			JS('__dict[key] = value')

	def __len__(self):
		__dict = self[...]
		return JS('Object.keys(__dict).length')

	def __getitem__(self, key):
		__dict = self[...]
		if JS("typeof(key) === 'object'"):
			JS('var uid = key.uid')
			return JS('__dict["@"+uid]')  ## "@" is needed so that integers can also be used as keys
		elif JS("typeof(key) === 'function'"):
			JS('var uid = key.uid')
			return JS('__dict["@"+uid]')  ## "@" is needed so that integers can also be used as keys
		else:
			return JS('__dict[key]')

	def __setitem__(self, key, value):
		global _PythonJS_UID

		__dict = self[...]
		if JS("typeof(key) === 'object'"):
			if JS("key.uid === undefined"):
				uid = _PythonJS_UID
				JS("key.uid = uid")
				_PythonJS_UID += 1
			JS('var uid = key.uid')
			JS('__dict["@"+uid] = value')
		elif JS("typeof(key) === 'function'"):
			if JS("key.uid === undefined"):
				uid = _PythonJS_UID
				JS("key.uid = uid")
				_PythonJS_UID += 1
			JS('var uid = key.uid')
			JS('__dict["@"+uid] = value')
		else:
			JS('__dict[key] = value')

	def keys(self):
		#__dict = self.js_object
		#__keys = JS('Object.keys(__dict)')  ## the problem with this is that keys are coerced into strings
		#out = list( js_object=__keys )  ## some bug in the translator prevents this
		#out.js_object = __keys  ## this style is deprecated
		#return out
		with javascript:
			arr = Object.keys( self[...] )
		return list( js_object=arr )

	def pop(self, key, d=None):
		v = self.get(key, None)
		if v is None:
			return d
		else:
			js_object = self[...]
			JS("delete js_object[key]")
			return v
		

	def values(self):
		__dict = self[...]
		__keys = JS('Object.keys(__dict)')
		out = list()
		i = 0
		while i < __keys.length:
			out.append( JS('__dict[ __keys[i] ]') )
			i += 1
		return out

	def __contains__(self, value):
		with javascript:
			keys = Object.keys(self[...])  ## the problem with this is that keys are coerced into strings
			if typeof(value) == 'object':
				key = '@'+value.uid
			else:
				key = ''+value  ## convert to string

			if keys.indexOf( key ) == -1:
				return False
			else:
				return True

	def __iter__(self):
		return Iterator(self.keys(), 0)



def set(a):
	'''
	This returns an array that is a minimal implementation of set.
	Often sets are used simply to remove duplicate entries from a list, 
	and then it get converted back to a list, it is safe to use fastset for this.

	The array prototype is overloaded with basic set functions:
		difference
		intersection
		issubset

	Note: sets in Python are not subscriptable, but can be iterated over.

	Python docs say that set are unordered, some programs may rely on this disorder
	for randomness, for sets of integers we emulate the unorder only uppon initalization 
	of the set, by masking the value by bits-1. Python implements sets starting with an 
	array of length 8, and mask of 7, if set length grows to 6 (3/4th), then it allocates 
	a new array of length 32 and mask of 31.  This is only emulated for arrays of 
	integers up to an array length of 1536.

	'''
	with javascript:
		if isinstance(a, list): a = a[...]
		hashtable = null
		if a.length <= 1536:
			hashtable = {}
			keys = []
			if a.length < 6:  ## hash array length 8
				mask = 7
			elif a.length < 22: ## 32
				mask = 31
			elif a.length < 86: ## 128
				mask = 127
			elif a.length < 342: ## 512
				mask = 511
			else: 				## 2048
				mask = 2047

		fallback = False
		if hashtable:
			for b in a:
				if typeof(b,'number') and b is (b|0):  ## set if integer
					key = b & mask
					hashtable[ key ] = b
					keys.push( key )
				else:
					fallback = True
					break

		else:
			fallback = True

		s = []

		if fallback:
			for item in a:
				if s.indexOf(item) == -1:
					s.push( item )
		else:
			keys.sort()
			for key in keys:
				s.push( hashtable[key] )

	return s


def frozenset(a):
	return set(a)





class array:
	## note that class-level dicts can only be used after the dict class has been defined above,
	## however, we can still not rely on using a dict here because dict creation relies on get_attribute,
	## and get_attribute relies on __NODEJS__ global variable to be set to False when inside NodeJS,
	## to be safe this is changed to use JSObjects
	with javascript:
		typecodes = {
			'c': 1, # char
			'b': 1, # signed char
			'B': 1, # unsigned char
			'u': 2, # unicode
			'h': 2, # signed short
			'H': 2, # unsigned short
			'i': 4, # signed int
			'I': 4, # unsigned int
			'l': 4, # signed long
			'L': 4, # unsigned long
			'f': 4, # float
			'd': 8, # double
			'float32':4,
			'float16':2,
			'float8' :1,

			'int32'  :4,
			'uint32' :4,
			'int16'  :2,
			'uint16' :2,
			'int8'  :1,
			'uint8' :1,
		}
		typecode_names = {
			'c': 'Int8',
			'b': 'Int8',
			'B': 'Uint8',
			'u': 'Uint16',
			'h': 'Int16',
			'H': 'Uint16',
			'i': 'Int32',
			'I': 'Uint32',
			#'l': 'TODO',
			#'L': 'TODO',
			'f': 'Float32',
			'd': 'Float64',

			'float32': 'Float32',
			'float16': 'Int16',
			'float8' : 'Int8',

			'int32'  : 'Int32',
			'uint32' : 'Uint32',
			'int16'  : 'Int16',
			'uint16' : 'Uint16',
			'int8'   : 'Int8',
			'uint8'  : 'Uint8',
		}

	def __init__(self, typecode, initializer=None, little_endian=False):
		self.typecode = typecode
		self.itemsize = self.typecodes[ typecode ]
		self.little_endian = little_endian

		if initializer:
			self.length = len(initializer)
			self.bytes = self.length * self.itemsize

			if self.typecode == 'float8':
				self._scale = max( [abs(min(initializer)), max(initializer)] )
				self._norm_get = self._scale / 127  ## half 8bits-1
				self._norm_set = 1.0 / self._norm_get
			elif self.typecode == 'float16':
				self._scale = max( [abs(min(initializer)), max(initializer)] )
				self._norm_get = self._scale / 32767  ## half 16bits-1
				self._norm_set = 1.0 / self._norm_get

		else:
			self.length = 0
			self.bytes = 0
		
		size = self.bytes
		buff = JS('new ArrayBuffer(size)')
		self.dataview = JS('new DataView(buff)')
		self.buffer = buff
		self.fromlist( initializer )

	def __len__(self):
		return self.length

	def __contains__(self, value):
		#lst = self.to_list()
		#return value in lst  ## this old style is deprecated
		arr = self.to_array()
		with javascript:
			if arr.indexOf(value) == -1: return False
			else: return True

	def __getitem__(self, index):
		step = self.itemsize
		offset = step * index

		dataview = self.dataview
		func_name = 'get'+self.typecode_names[ self.typecode ]
		func = JS('dataview[func_name].bind(dataview)')

		if offset < self.bytes:
			value = JS('func(offset)')
			if self.typecode == 'float8':
				value = value * self._norm_get
			elif self.typecode == 'float16':
				value = value * self._norm_get
			return value
		else:
			raise IndexError

	def __setitem__(self, index, value):
		step = self.itemsize
		if index < 0: index = self.length + index -1  ## TODO fixme
		offset = step * index

		dataview = self.dataview
		func_name = 'set'+self.typecode_names[ self.typecode ]
		func = JS('dataview[func_name].bind(dataview)')

		if offset < self.bytes:
			if self.typecode == 'float8':
				value = value * self._norm_set
			elif self.typecode == 'float16':
				value = value * self._norm_set

			JS('func(offset, value)')
		else:
			raise IndexError

	def __iter__(self):
		return Iterator(self, 0)

	def get(self, index):
		return self[ index ]

	def fromlist(self, lst):
		length = len(lst)
		step = self.itemsize
		typecode = self.typecode
		size = length * step
		dataview = self.dataview
		func_name = 'set'+self.typecode_names[ typecode ]
		func = JS('dataview[func_name].bind(dataview)')
		if size <= self.bytes:
			i = 0; offset = 0
			while i < length:
				item = lst[i]
				if typecode == 'float8':
					item *= self._norm_set
				elif typecode == 'float16':
					item *= self._norm_set

				JS('func(offset,item)')
				offset += step
				i += 1
		else:
			raise TypeError

	def resize(self, length):
		buff = self.buffer
		source = JS('new Uint8Array(buff)')

		new_size = length * self.itemsize
		new_buff = JS('new ArrayBuffer(new_size)')
		target = JS('new Uint8Array(new_buff)')
		JS('target.set(source)')

		self.length = length
		self.bytes = new_size
		self.buffer = new_buff
		self.dataview = JS('new DataView(new_buff)')

	def append(self, value):
		length = self.length
		self.resize( self.length + 1 )
		self[ length ] = value

	def extend(self, lst):  ## TODO optimize
		for value in lst:
			self.append( value )

	def to_array(self):
		arr = JSArray()
		i = 0
		while i < self.length:
			item = self[i]
			JS('arr.push( item )')
			i += 1
		return arr

	def to_list(self):
		return list( js_object=self.to_array() )

	def to_ascii(self):
		string = ''
		arr = self.to_array()
		i = 0; length = arr.length
		while i < length:
			JS('var num = arr[i]')
			JS('var char = String.fromCharCode(num)')
			string += char
			i += 1
		return string


# JSON stuff

with javascript:
	json = {
		'loads': lambda s: JSON.parse(s),
		'dumps': lambda o: JSON.stringify(o)
	}

def _to_pythonjs(json):
	var(jstype, item, output)
	jstype = JS('typeof json')
	if jstype == 'number':
		return json
	if jstype == 'string':
		return json
	if JS("Object.prototype.toString.call(json) === '[object Array]'"):
		output = list()
		raw = list( js_object=json )
		var(append)
		append = output.append
		for item in raw:
			append(_to_pythonjs(item))
		return output
	# else it's a map
	output = dict()
	var(set)
	set = output.set
	keys = list( js_object=JS('Object.keys(json)') )
	for key in keys:
		set(key, _to_pythonjs(JS("json[key]")))
	return output

def json_to_pythonjs(json):
	return _to_pythonjs(JSON.parse(json))

# inverse function

def _to_json(pythonjs):
	if isinstance(pythonjs, list):
		r = JSArray()
		for i in pythonjs:
			r.push(_to_json(i))
	elif isinstance(pythonjs, dict):
		var(r)
		r = JSObject()
		for key in pythonjs.keys():
			value = _to_json(pythonjs.get(key))
			key = _to_json(key)
			with javascript:
				r[key] = value
	else:
		r = pythonjs
	return r


def pythonjs_to_json(pythonjs):
	return JSON.stringify(_to_json(pythonjs))
