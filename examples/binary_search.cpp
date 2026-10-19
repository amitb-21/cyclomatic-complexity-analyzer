#include <iostream>

int main()
{
    int values[] = {1, 3, 5, 7, 9, 11, 13};
    int target = 11;
    int left = 0;
    int right = 6;

    while (left <= right)
    {
        int middle = left + (right - left) / 2;

        if (values[middle] == target)
        {
            return 0;
        }
        else if (values[middle] < target)
        {
            left = middle + 1;
        }
        else
        {
            right = middle - 1;
        }
    }

    return 1;
}