// Section 1
const express = require('express');
const axios = require('axios');
// const cors = require('cors');
const path = require('path');
// Section 2
const app = express();
const port = process.env.PORT || 3000;
app.use(express.static(path.join(__dirname, '..','public')));
// app.use(cors());
// Section 3
app.get('/', (req, res) => { 
 res.send("<h1>Home page</h1>");
});
app.get('/users', (req, res) => {
    axios.get('https://randomuser.me/api/?page=1&results=30')
     .then(response => {
       res.send(response.data);
     });
   });
// Section 4
app.listen(port, () => {
 console.log('server started on port', port);
});