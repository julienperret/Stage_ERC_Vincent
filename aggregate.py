def slidingWin(array, row, col, size=3, calc='sum'):
    if (row > size - 1 and row + size-1 < rows) and (col > size - 1 and col + size-1 < cols):
        s = 0
        pos = [i + 1 for i in range(- size//2, size//2)]
        for r in pos:
            for c in pos:
                s += array[row + r][col + c]
        if calc == 'sum':
            return s
        elif calc == 'mean':
            return s / (size * size)
    else:
        return None



def aggregate(array, resolution):
    rows, cols = array.shape
    out_array = np.zeros([rows//resolution, cols//resolution])
    for row in range(rows//resolution):
        for col in range(cols//resolution):
            print('row : ' + str(row)  + '\ncol : ' + str(col))
            ir, ic = 0 + row * resolution, 0 + col * resolution
            for r in range(ir, ir + resolution):
                for c in range(ic, ic + resolution):
                    print('r : ' + str(r) + '\nc : ' + str(c))
                    if r < array.shape[0] and c < array.shape[1]:
                        out_array[row][col] += array[r][c]

    return out_array
