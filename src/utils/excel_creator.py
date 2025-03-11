import pandas as pd

# Define the player data
data = {
    "First_Name": [
        "Swade", "Dillon", "Jonathan", "Tyrell", "Daniel",
        "Chadarius", "Irv", "Major", "Giles", "Hunter",
        "Sean", "Joseph", "Kedrick", "Jacob", "Cam",
        "Elliot", "Bradley", "Hunter", "Deonte"
    ],
    "Last_Name": [
        "Hutchinson", "Lee", "Rice", "Shavers", "Skehan",
        "Townsend", "Smith Jr.", "Tennison", "Amos", "Bryant",
        "Goodman", "Harvey", "James", "Parker", "Stewart",
        "Baker", "Bozeman", "Brannon", "Brown"
    ],
    "Twitter": [None] * 19,
    "Facebook": [None] * 19,
    "Instagram": [None] * 19,
    "Email": [None] * 19,
    "Phone": [None] * 19,
}

# Create a DataFrame with the player data
df = pd.DataFrame(data)

# Save the DataFrame to an Excel file
output_file = "test_players.xlsx"
df.to_excel(output_file, index=False)

print(f"{output_file} has been created!")


# data = {
#     "First_Name": [
#         "Swade", "Dillon", "Jonathan", "Tyrell", "Daniel",
#         "Chadarius", "Irv", "Major", "Giles", "Hunter",
#         "Sean", "Joseph", "Kedrick", "Jacob", "Cam",
#         "Elliot", "Bradley", "Hunter", "Deonte"
#     ],
#     "Last_Name": [
#         "Hutchinson", "Lee", "Rice", "Shavers", "Skehan",
#         "Townsend", "Smith Jr.", "Tennison", "Amos", "Bryant",
#         "Goodman", "Harvey", "James", "Parker", "Stewart",
#         "Baker", "Bozeman", "Brannon", "Brown"
#     ],
#     "Twitter": [None] * 19,
#     "Facebook": [None] * 19,
#     "Instagram": [None] * 19,
#     "Email": [None] * 19,
#     "Phone": [None] * 19,
# }