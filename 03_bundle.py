"""Inline data/processed/data.json into web/template.html -> dist/index.html"""
import os; os.makedirs('dist',exist_ok=True)
t=open('web/template.html').read().replace('__DATA__',open('data/processed/data.json').read())
open('dist/index.html','w').write(t); print('dist/index.html',len(t))
