# COUNTER

This code is a very simple counting system that can be displayed on OBS.

The script generates a text file countaning a sample text and an increment. Every time the script is run, the increment is augmented. 
If the count doesnt exist or is different from the sample text, then the count is reset. 

There is 2 different scripts. The main one is ``` counter.py ```, it generates the ``` count.txt ``` based on the ``` sample.txt ```, and finally ``` reset.py ``` resets the count by erasing the ``` count.txt ``` file and running the ``` counter.py ```. 

``` [?] ``` symbol is used to define where the incrementation should be placed in the ``` sample.txt ``` file. 

---

## SETUP 

- 1 - Be sure to have Python
- 2 - Run ``` counter.py ```
- 3 - Check the creation of ``` count.txt ```

## SETUP IN OBS 

- 1 - Creating a Text Source.
- 2 - Change the Properties for the text to be read from a file. 
- 3 - Modify, Customize, and place it as you wish. 

## SETUP IN STREAMDECK 

- 1 - Create an "OPEN" Action under the System Tab. 
- 2 - Point the action to the ``` counter.py ``` script.
- 3 - **OPTIONAL** - Do the same for the ``` reset.py ``` Script