# -*- coding: utf-8 -*-
"""Stocks_BeautifulSoup

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1Gzf5sj3yZyDu9pBmeJ3DLGAC1pxRwDkO

#Name: Mayank Ambalal Jain
## ID: 1001761066
"""

# Importing libraries
import time
import os.path
from bs4 import BeautifulSoup
import requests
import urllib.request


#  Scarping the target website with soup
url_Stocks = 'https://money.cnn.com/data/hotstocks/'
res = urllib.request.urlopen(url_Stocks) 
soup = BeautifulSoup(res, 'html.parser')

#  To store the parsed soup in a dict & extracting the data

dict_Stocks = {}

symbol = soup.find_all('a', attrs={'class':'wsod_symbol'})

ticker_List = []
i = 0
for t in symbol:
  if i<3:
    i+=1
    continue
  ticker_List.append(t.text)
  i+=1

findTitle = soup.find_all('table', attrs = {'class': 'wsod_dataTable wsod_dataTableBigAlt'})

# Data extraction of company names
names_List = []

for m in findTitle:
  findRows = m.find_all('tr')
  for n in findRows:
    findTitle = n.find_all('span')
    i = 0
    for o in findTitle:
      if i%6 == 0:
        names_List.append(o.text)
      i+=1

# Looping over the ticker list for getting dict. of company names with their tickers
i = 0
for item in ticker_List:
  dict_Stocks[item] = names_List[i]
  i+=1

print("This is a program to scrape data from the https://money.cnn.com/data/hotstocks/  for a class project.")

# Displaying the top ten most active , gainers and losers by iterating ticker and dict list.
i=0
print('Most Actives')
while(i<10):
    item = ticker_List[i]
    print(item,"\t",dict_Stocks[item])
    i+=1
print()
print('Gainers')
while(i<20):
    item=ticker_List[i]
    print(item,"\t",dict_Stocks[item])
    i+=1
print()
print('Losers')
while(i<30):
    item=ticker_List[i]
    print(item,"\t",dict_Stocks[item])
    i+=1
time.sleep(1)

fd = open('stocks.csv','w')
fd.close()
#  writing the most active, gainers and losers file.
for idx,stk in enumerate(ticker_List):
  dataPoint1 = []
  allStock = 'https://money.cnn.com/quote/quote.html?symb='+stk
  res1 = urllib.request.urlopen(allStock)
  soup1 = BeautifulSoup(res1, 'html.parser')
  dataPoint1 = soup1.find_all('td', attrs={'class': 'wsod_quoteDataPoint'})

  usrStkList1 = []
  iterate = [0,1,3,5]
  i = 0

# looping over the datapoint to find data
  for m in dataPoint1:
    if i in iterate:
      usrStkList1.append(m.text)
    i+=1
  with open('stocks.csv','a') as fd:
    if idx<10:
      fd.write(','.join(["Most Actives", stk, dict_Stocks[stk], usrStkList1[0],usrStkList1[1],'"'+ usrStkList1[2]+'"',usrStkList1[3]])+'\n')
    if idx>9 and idx<20:
      fd.write(','.join(["Gainers", stk, dict_Stocks[stk], usrStkList1[0],usrStkList1[1],'"'+ usrStkList1[2]+'"',usrStkList1[3]])+'\n')
    if idx>19 and idx<30:
      fd.write(','.join(["Losers", stk, dict_Stocks[stk], usrStkList1[0],usrStkList1[1],'"'+ usrStkList1[2]+'"',usrStkList1[3]])+'\n')

#  Taking user Input and considering that input should be captial
print()
userIn=input("Which stock are you interested in: ")
print()
 

#  Validation of input
try:
  # scraping the  user data with soup
  userStock = 'https://money.cnn.com/quote/quote.html?symb='+userIn
  res = urllib.request.urlopen(userStock)
  soup = BeautifulSoup(res, 'html.parser')

  usrStkList = []
  dataPoint = soup.find_all('td', attrs={'class': 'wsod_quoteDataPoint'})
  iterate = [0,1,3,5]
  i = 0
  # looping over the datapoint to find data
  for m in dataPoint:
    if i in iterate:
      usrStkList.append(m.text)
    i+=1
  
  # User Input Data Print

  print('The data for ',userIn," ",dict_Stocks[userIn]," is the following: ")
  print(userIn,"\t",dict_Stocks[userIn])
  print("OPEN","\t\t",usrStkList[0])
  print("PREV CLOSE","\t",usrStkList[1])
  print("VOLUME","\t\t",usrStkList[2])
  print("MARKET CAP","\t",usrStkList[3])


except:
      print("Couldnt find the company ticker. Check spelling and case sensitivity.")

