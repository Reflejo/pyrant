# pyrant
A Pythonic implementation of Tokyo Tyrant protocol

### Note: This project is now mantained [here](https://bitbucket.org/neithere/pyrant/issues)
  

Tokyo Cabinet is a fast and light-weight database library that manages a key-value store, and Tokyo Cabinet is a companion lightweight database server. The pyrant module provides a Pythonic interface, as well as a low-level interface, to the Tokyo Tyrant protocol, and allows for easy interfacing to a Tokyo Cabinet database from Python.

Example usage of the module (interfacing to a Tokyo Tyrant table database):

```python
>>> import pyrant
>>> t = pyrant.Tyrant(host='127.0.0.1', port=1978)
>>> t['key'] = {'name': 'foo'}
>>> print t['key']['name']
foo
>>> del t['key']
>>> print t['key']
Traceback (most recent call last):
    ...
KeyError: 'key'
```

### Documentation

Find more information about Tokyo Cabinet and Tokyo Tyrant on: <http://fallabs.com/tokyotyrant/>

Documentation for pyrant is available online at <http://packages.python.org/pyrant/>. The official module versions are made avaliable at <http://pypi.python.org/pypi/pyrant/>, but you are welcome to grab a snapshot of the source code from this repository. Note for all versions: Python 2.4+ is required.

The main purpose of this wiki is to support the continuous development of pyrant.

### Developer ressources

 * [All issues](https://bitbucket.org/neithere/pyrant/issues)
 * [Tokyo Cabinet discussion group](https://groups.google.com/forum/?fromgroups#!forum/tokyocabinet-users)
 * [Unofficial Tokyo Cabinet wiki](http://tokyocabinetwiki.pbworks.com/w/page/23739738/FrontPage)
