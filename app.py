import streamlit as st
import torch
import torch.nn as nn
import torchvision.models as models
import PIL
from torchvision import transforms
import numpy as np
from labels import labels_dict
import easyocr
import datetime
import psycopg2



def default_device():
    '''Indicate availablibity of GPU, otherwise return CPU'''
    if torch.cuda.is_available():
        return torch.device('cuda')
    else:
        return torch.device('cpu')


def to_device(tensorss, device):
    '''Move tensor to chosen device'''
    if isinstance(tensorss, (list, tuple)):
        return [to_device(x, device) for x in tensorss]
    return tensorss.to(device, non_blocking=True)


class DeviceDataloader():
    '''Wrap DataLoader to move the model to device'''

    def __init__(self, dl, device):
        self.dl = dl
        self.device = device

    def __iter__(self):
        '''Yield batch of data after moving the data to a device'''
        for batch in self.dl:
            yield to_device(batch, self.device)

    def __len__(self):
        '''Return number of batches'''
        return len(self.dl)


# Check available device type
device = default_device()


class MultilabelImageClassificationBase(nn.Module):
    def training_step(self, batch):
        image, label = batch
        out = self  # prediction generated
        loss = F.cross_entropy(out, label)  # Calculate loss using cross_entropy
        return loss

    def validation_step(self, batch):
        image, label = batch
        out = self  # predictioon generated
        loss = F.cross_entropy(out, label)  # Calculate loss using cross_entropy
        acc = accuracy(out, label)
        return {'val_loss': loss.detach(), 'val_acc': acc}

    def validation_epoch_end(self, output):
        '''at the end of epoch, return average score (accuracy and cross entropy loss)'''
        batch_loss = [x['val_loss'] for x in output]
        epoch_loss = torch.stack(batch_loss).mean()

        batch_accs = [x['val_acc'] for x in output]
        epoch_acc = torch.stack(batch_accs).mean()
        return {'val_loss': epoch_loss.item(), 'val_acc': epoch_acc.item()}

    def epoch_end(self, epoch, result):
        '''Print out the score (accuracy and cross entropy loss) at the end of the epoch'''
        # result recorded using evaluate function
        print("Epoch [{}], train_loss: {:}, val_loss: {:}, val_acc: {:}".format(
            epoch, result['train_loss'], result['val_loss'], result['val_acc']))


class Resnet50(MultilabelImageClassificationBase):
    def __init__(self):
        super().__init__()
        # Use a pretrained model
        self.network = models.resnet50(pretrained=True)
        # Replace last layer
        num_ftrs = self.network.fc.in_features
        self.network.fc = nn.Linear(num_ftrs, 196)

    def forward(self, xb):
        return self.network(xb)


model = to_device(Resnet50(), device)

path = "car_model.pt"
car_model = torch.load(path, map_location=torch.device('cpu'))

def current_time():
    return datetime.datetime.now().replace(microsecond=0)

def car_recogniser_entrance(our_img):
    # Establishing the connection
    conn = psycopg2.connect(
        database="vehicle", user='postgres', password='abc123', host='127.0.0.1', port='5432'
    )
    # Setting auto commit false
    conn.autocommit = True

    # Creating a cursor object using the cursor() method
    cursor = conn.cursor()

    car_image = our_img

    trans = transforms.Compose([
        transforms.Resize((400, 400)),
        transforms.RandomRotation(15),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.RandomErasing(inplace=True),
        transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
    ])

    # preprocessing for prediction image
    input = trans(car_image)
    input = input.view(1, 3, 400, 400)

    output = car_model(input)

    prediction = int(torch.max(output.data, 1)[1].numpy())



    # return prediction label
    predicted_val = ([value for value in labels_dict.values()][prediction])
    st.text("Detected vehicle model: ")
    predicted_val

    # converting PIL object into numpy array for ocr
    new_array = np.array(car_image)
    reader = easyocr.Reader(['en'], gpu=False)
    bounds = reader.readtext(new_array, detail=0)

    st.text("Detected license plate number: ")
    num_plate = ' '.join([str(elem) for elem in bounds])
    num_plate

    enter_time = current_time()
    st.text("The vehicle enter the parking at:")
    enter_time
    time_enter = enter_time.strftime("%Y/%m/%d, %H:%M:%S")


    sql = """INSERT INTO vehicle_data_entrance(vehicle_brand, plate_number, enter_time) VALUES(%s,%s,%s)"""
    record_to_enter = (predicted_val, num_plate, time_enter)
    cursor.execute(sql,record_to_enter)
    conn.commit()
    cursor.close()
    conn.close()

def car_recogniser_exit(our_img):
    # Establishing the connection
    conn = psycopg2.connect(
        database="vehicle", user='postgres', password='abc123', host='127.0.0.1', port='5432'
    )
    # Setting auto commit false
    conn.autocommit = True

    # Creating a cursor object using the cursor() method
    cursor = conn.cursor()

    car_image = our_img

    trans = transforms.Compose([
        transforms.Resize((400, 400)),
        transforms.RandomRotation(15),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        # transforms.RandomErasing(inplace=True),
        transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
    ])

    # preprocessing for prediction image
    input = trans(car_image)
    input = input.view(1, 3, 400, 400)

    output = car_model(input)

    prediction = int(torch.max(output.data, 1)[1].numpy())



    # return prediction label
    predicted_val = ([value for value in labels_dict.values()][prediction])
    st.text("Detected vehicle model: ")
    predicted_val

    # converting PIL object into numpy array for ocr
    new_array = np.array(car_image)
    reader = easyocr.Reader(['en'], gpu=False)
    bounds = reader.readtext(new_array, detail=0)

    st.text("Detected license plate number: ")
    num_plate = ' '.join([str(elem) for elem in bounds])
    num_plate

    ext_time = current_time()
    st.text("The vehicle enter the parking at:")
    ext_time
    time_exit = ext_time.strftime("%Y/%m/%d, %H:%M:%S")


    sql = """INSERT INTO vehicle_data_exit(vehicle_brand, plate_number, exit_time) VALUES(%s,%s,%s)"""
    record_to_enter = (predicted_val, num_plate, time_exit)
    cursor.execute(sql,record_to_enter)
    conn.commit()
    cursor.close()
    conn.close()

def car_detection_entrance():
    global our_image
    html_temp = """
        <body style="background-color:red;">
        <div style="background-color:teal ;padding:10px">
        <h2 style="color:white;text-align:center;">Intelligent Car Park Management System</h2>
        </div>
        </body>
        """
    st.markdown(html_temp, unsafe_allow_html=True)
    st.set_option('deprecation.showfileUploaderEncoding', False)

    image_file = st.file_uploader("Upload Image", type=['jpg', 'png', 'jpeg'])
    if image_file is not None:
        our_image = PIL.Image.open(image_file)
        st.text("Original Image")
        st.image(our_image)

    if st.button("Recognise"):
        car_recogniser_entrance(our_image)



def car_detection_exit():
    global our_image
    html_temp = """
        <body style="background-color:red;">
        <div style="background-color:teal ;padding:10px">
        <h2 style="color:white;text-align:center;">Intelligent Car Park Management System</h2>
        </div>
        </body>
        """
    st.markdown(html_temp, unsafe_allow_html=True)
    st.set_option('deprecation.showfileUploaderEncoding', False)

    image_file = st.file_uploader("Upload Image", type=['jpg', 'png', 'jpeg'])
    if image_file is not None:
        our_image = PIL.Image.open(image_file)
        st.text("Original Image")
        st.image(our_image)

    if st.button("Recognise"):
        car_recogniser_exit(our_image)

# option at the side bar
options = st.sidebar.selectbox('Select an Option', ['Parking Entrance', 'Parking Exit', 'Parking Fee Calculation'])

# title
st.set_option('deprecation.showfileUploaderEncoding', False)

if options == 'Parking Entrance':

    st.title("Car Model + License Plate Recognition for Parking Entrance")
    car_detection_entrance()


elif options == 'Parking Exit':

    st.title("Car Model + License Plate Recognition for Parking Exit")
    car_detection_exit()





elif options == 'Parking Fee Calculation':

    # Establishing the connection
    conn = psycopg2.connect(
        database="vehicle", user='postgres', password='abc123', host='127.0.0.1', port='5432'
    )
    # Setting auto commit false
    conn.autocommit = True

    # Creating a cursor object using the cursor() method
    cursor = conn.cursor()

    st.title("Parking Fee Calculation")
    html_temp = """
        <body style="background-color:red;">
        <div style="background-color:teal ;padding:10px">
        <h2 style="color:white;text-align:center;">Intelligent Car Park Management System</h2>
        </div>
        </body>
        """
    st.markdown(html_temp, unsafe_allow_html=True)
    st.set_option('deprecation.showfileUploaderEncoding', False)

    sql = """select concat_ws(',', vehicle_data_entrance.vehicle_brand,vehicle_data_entrance.plate_number)
             as vehicle_info from vehicle_data_entrance order by vehicle_data_entrance.plate_number """

    cursor.execute(sql)

    result = [i[0] for i in cursor.fetchall()]

    dropdown = st.selectbox('Which vehicle you would like to choose?', (result))

    st.text("Vehicle Entrance Time:")



    st.text("Vehicle Exit Time:")


    # shows the calculation of parking duration and fee
    st.text("Total parking duration (in minutes):")


    # st.header("Total Parking Fee:")
    # if 0 <= duration <= 15:
    #     st.subheader("Parking fee is free. No payment needed. :oncoming_automobile:")
    #
    # elif 15 <= duration <= 60:
    #     fee = 2.00
    #     st.subheader("Parking fee for {} minutes is RM {:.2f} :oncoming_automobile:".format(duration, fee))
    #
    # elif 60 <= duration <= 120:
    #     fee = 3.00
    #     st.subheader("Parking fee for {} minutes is RM {:.2f} :oncoming_automobile:".format(duration, fee))
    #
    # elif 120 <= duration <= 180 :
    #     fee = 4.00
    #     st.subheader("Parking fee for {} minutes is RM {:.2f} :oncoming_automobile:".format(duration, fee))
    #
    # elif 180 <= duration <= 240 :
    #     fee = 5.00
    #     st.subheader("Parking fee for {} minutes is RM {:.2f} :oncoming_automobile:".format(duration, fee))
    #
    # elif 240 <= duration <= 300:
    #     fee = 6.00
    #     st.subheader("Parking fee for {} minutes is RM {:.2f} :oncoming_automobile:".format(duration, fee))
    #
    # elif 300 <= duration <= 360:
    #     fee = 7.00
    #     st.subheader("Parking fee for {} minutes is RM {:.2f} :oncoming_automobile:".format(duration, fee))
    #
    # elif 360 <= duration <= 420:
    #     fee = 8.00
    #     st.subheader("Parking fee for {} minutes is RM {:.2f} :oncoming_automobile:".format(duration, fee))
    #
    # elif 420 <= duration <= 480:
    #     fee = 9.00
    #     st.subheader("Parking fee for {} minutes is RM {:.2f} :oncoming_automobile:".format(duration, fee))
    #
    # else:
    #     fee = 10.00
    #     st.subheader("Parking for {} minutes is RM {:.2f} :oncoming_automobile:".format(duration, fee))

else:
    st.text("The option is not exist. Please try again.")