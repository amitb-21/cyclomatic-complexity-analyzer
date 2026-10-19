
def classify_numbers(numbers):
    total = 0

    for number in numbers:
        if number < 0:
            continue

        if number == 0 or number == 1:
            total += 1
        elif number > 10 and number < 100:
            total += 2
        else:
            total += 3

    while total > 50:
        if total > 100:
            break
        total -= 5

    return total


result = classify_numbers([0, 1, 5, 15, 25, -3])
print(result)
