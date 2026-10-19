#include <iostream>

int main()
{
    int values[] = {-2, 1, -3, 4, -1, 2, 1, -5, 4};
    int current_max = values[0];
    int best = values[0];

    for (int i = 1; i < 9; i++)
    {
        if (current_max < 0)
        {
            current_max = values[i];
        }
        else
        {
            current_max += values[i];
        }

        if (current_max > best)
        {
            best = current_max;
        }
    }

    return best == 6 ? 0 : 1;
}