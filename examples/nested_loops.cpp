int main()
{
    int i = 0;

    while (i < 3)
    {
        int j = 0;

        while (j < 2)
        {
            j++;

            if (j == 1)
            {
                continue;
            }
        }

        i++;
    }

    return 0;
}