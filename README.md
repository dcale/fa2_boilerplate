FA2 Boilerplate SmartContract
====================================



Build/Basic Usage
-----------------

## SmartPy Online IDE Development

You can simply copy/paste the raw payload/code from fa2_boilerplate.py to https://smartpy.io/ide 

## Local Development

### Dependencies

This project depends only on SmartPy, you can install SmartPy by doing a:

```
$ curl -s https://SmartPy.io/dev/cli/SmartPy.sh -o /tmp/SmartPy.sh
$ chmod +x /tmp/SmartPy.sh
$ /tmp/SmartPy.sh local-install-auto smartpy
```

### Build

```
$ ./smartpy/SmartPy.sh compile fa2_boilerplate.py "MintableFA2('<<admin address>>')" out
```

### Test
```
$ ./smartpy/SmartPy.sh test fa2_boilerplate.py out
```