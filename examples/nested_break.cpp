int main()
{
    int i = 0;

    while (i < 3)
    {
        int j = 0;

        while (j < 5)
        {
            j++;

            if (j == 2)
            {
                break;
            }
        }

        i++;
    }

    return 0;
}