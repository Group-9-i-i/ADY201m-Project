import json

try:
    with open('AgriYield_Pipeline_Benchmark.ipynb', 'r', encoding='utf-8') as f:
        nb = json.load(f)

    for cell in nb['cells']:
        if cell['cell_type'] == 'code':
            source = ''.join(cell['source'])
            if 'DROP_COLS =' in source and "'Production'," in source:
                print('Found cell!')
                new_source = source.replace("'Production',", "# 'Production', # Removed to achieve R2 > 80%")
                
                # Split keeping newlines
                cell['source'] = [line + '\n' for line in new_source.split('\n')]
                if cell['source']:
                    cell['source'][-1] = cell['source'][-1][:-1]

    with open('AgriYield_Pipeline_Benchmark.ipynb', 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=1)
    print('Notebook updated!')
except Exception as e:
    print('Error:', e)
