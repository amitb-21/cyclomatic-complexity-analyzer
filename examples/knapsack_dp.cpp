#include <iostream>

int main()
{
    int weights[] = {1, 3, 4, 5};
    int values[] = {1, 4, 5, 7};
    int capacity = 7;
    int best[5][8] = {};

    for (int item = 1; item <= 4; item++)
    {
        for (int current_capacity = 0; current_capacity <= capacity; current_capacity++)
        {
            best[item][current_capacity] = best[item - 1][current_capacity];

            if (weights[item - 1] <= current_capacity)
            {
                int included_value = values[item - 1] + best[item - 1][current_capacity - weights[item - 1]];

                if (included_value > best[item][current_capacity])
                {
                    best[item][current_capacity] = included_value;
                }
            }
        }
    }

    return best[4][capacity] == 9 ? 0 : 1;
}